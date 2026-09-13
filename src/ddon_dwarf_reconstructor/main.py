"""Generation workflow used by the typed command-line boundary."""

from __future__ import annotations

import os
import sys
from logging import Logger
from pathlib import Path
from uuid import uuid4

from .application.generation.logging_workflow import (
    log_generation_options as _log_options,
)
from .application.generation.logging_workflow import log_generation_summary as _log_summary
from .application.generation.options import (
    GenerationOptions,
)
from .application.generation.options import (
    validate_implementation_options as _validate_implementation_options,
)
from .application.generators import (
    DwarfGenerator,
    GenerationOutcome,
    GenerationReport,
    SymbolExtractionRequest,
    SymbolExtractionResult,
)
from .application.generators.generation_contracts import GenerationStatus
from .application.generators.session import DwarfSessionFactory
from .core.observability import bind_context, get_logger, log_event, log_exception
from .domain.models.tool_evidence import ToolExport
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.composition import (
    create_disassembly_factory,
    create_dump_lookup,
    create_dwarf_session,
)
from .infrastructure.config import Config, DwarfRuntimeConfig, get_cache_file_path
from .infrastructure.logging import LoggerSetup
from .infrastructure.symbol_output import SymbolPublisher
from .infrastructure.toolchain_exports import load_tool_exports


def _load_config(options: GenerationOptions) -> Config:
    config = Config.from_args(
        elf_file_path=options.elf_file,
        output_dir=options.output,
        verbose=options.verbose,
    )
    if (
        _is_symbol_generation(options)
        and options.output is None
        and os.getenv("OUTPUT_DIR") is None
    ):
        config.output_dir = Path("generated")
    config.validate()
    return config


def _is_symbol_generation(options: GenerationOptions) -> bool:
    """Return whether this is the unified C++/assembly symbol-generation route."""
    return options.export_knowledge is None


def _validate_store_options(options: GenerationOptions) -> None:
    """Require a pre-materialized store for normal generation commands."""
    if options.dwarf_store_manifest is None:
        raise ValueError(
            "Generation requires --dwarf-store; materialize the ELF and load the complete "
            "manifest with artifacts load-doris first"
        )
    if options.dwarf_dump is not None or options.dwarf_index is not None:
        raise ValueError(
            "--dwarf-dump and --dwarf-index are validation-only and cannot drive generation"
        )


def _read_symbols(options: GenerationOptions, logger: Logger) -> list[str]:
    if options.symbols and options.symbols_file:
        raise ValueError("Cannot use both --symbol and --symbols-file options")
    if options.symbols:
        symbols = [symbol.strip() for symbol in options.symbols if symbol.strip()]
    elif options.symbols_file:
        symbols = _read_symbol_file(options.symbols_file, logger)
    else:
        raise ValueError("Must provide either --symbol or --symbols-file option")
    if not symbols:
        raise ValueError("No symbols provided")
    _validate_unique_symbols(symbols)
    return symbols


def _validate_unique_symbols(symbols: list[str]) -> None:
    seen: set[str] = set()
    for symbol in symbols:
        if symbol in seen:
            raise ValueError(f"Duplicate symbol provided: {symbol}")
        seen.add(symbol)


def _read_symbol_file(path: Path, logger: Logger) -> list[str]:
    try:
        with path.open(encoding="utf-8") as symbol_file:
            symbols = [
                line.strip()
                for line in symbol_file
                if line.strip() and not line.strip().startswith("#")
            ]
        log_event(logger, 20, "symbols_file_read", path=path, symbol_count=len(symbols))
        return symbols
    except FileNotFoundError as error:
        raise ValueError(f"Symbols file not found: {path}") from error
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Error reading symbols file: {error}") from error


def _run_generation(
    options: GenerationOptions, config: Config, symbols: list[str], logger: Logger
) -> tuple[int, list[tuple[str, str]]]:
    try:
        return _run_generation_impl(options, config, symbols, logger)
    except Exception as error:
        raise RuntimeError(f"Fatal error during generation: {error}") from error


def _run_generation_impl(
    options: GenerationOptions, config: Config, symbols: list[str], logger: Logger
) -> tuple[int, list[tuple[str, str]]]:
    dwarf_config = DwarfRuntimeConfig.from_environment()
    identity_catalog = SourceIdentityCatalog()
    tool_exports = load_tool_exports(
        options.tool_export_manifests,
        config.elf_file_path,
        identity_catalog,
    )
    session_factory = _session_factory(
        options, config.elf_file_path, get_cache_file_path(str(config.elf_file_path))
    )
    with DwarfGenerator(
        config.elf_file_path,
        session_factory=session_factory,
        exhaustive_search=options.exhaustive,
        dwarf_dump_path=options.dwarf_dump,
        dwarf_index_path=options.dwarf_index,
        resolve_param_names=options.resolve_param_names,
        dump_lookup_factory=create_dump_lookup,
        disassembly_factory=create_disassembly_factory(
            options.llvm_readobj,
            options.llvm_objdump,
            options.llvm_target_triple,
        ),
        cache_file=get_cache_file_path(str(config.elf_file_path)),
        die_cache_size=dwarf_config.die_cache_size,
        type_cache_size=dwarf_config.type_cache_size,
        search_timeout=dwarf_config.search_timeout_seconds,
        source_hash=identity_catalog.sha256,
        source_identity=identity_catalog,
    ) as generator:
        if _is_symbol_generation(options):
            return _run_symbol_generation(
                options,
                config,
                generator,
                symbols,
                logger,
                identity_catalog,
            )
        return _run_knowledge_export(options, config, generator, symbols, logger, tool_exports)


def _run_symbol_generation(
    options: GenerationOptions,
    config: Config,
    generator: DwarfGenerator,
    symbols: list[str],
    logger: Logger,
    identity_catalog: SourceIdentityCatalog,
) -> tuple[int, list[tuple[str, str]]]:
    """Resolve one symbol request once and publish its deduplicated flat artifacts."""
    generator.begin_root("symbols")
    try:
        symbol_set = generator.extract_symbols(SymbolExtractionRequest(tuple(symbols)))
        publisher, source_sha256, target = _publish_symbol_headers(
            options, config, generator, symbol_set, identity_catalog
        )
        implementation_report = (
            generator.discover_implementations_for_symbols(
                tuple(symbols),
                symbol_set,
                orbis_objdump_path=options.orbis_objdump,
            )
            if options.extract_assembly
            else None
        )
        if implementation_report is not None:
            target = publisher.publish(
                config.output_dir,
                generator.platform,
                config.elf_file_path,
                source_sha256,
                symbol_set,
                implementation_report,
                emit_assembly=True,
                emit_sources=options.emit_implementation_sources,
                generate_context=options.generate_context,
            )
        outcomes, failures = _symbol_generation_outcomes(symbols, symbol_set)
        generation_report = GenerationReport(
            requested_symbols=tuple(symbols),
            outcomes=outcomes,
            published=True,
        )
        log_event(
            logger,
            20 if not failures else 30,
            "generation_report",
            fields=generation_report.to_dict(),
        )
        log_event(
            logger,
            20,
            "symbols_published",
            output_dir=target,
            symbol_count=len(symbols),
            header_count=symbol_set.header_count,
            class_count=symbol_set.class_count,
            assembly_count=(
                sum(bool(method.instructions) for method in implementation_report.methods)
                if implementation_report is not None
                else 0
            ),
            context_generated=options.generate_context,
        )
        return len(symbols) - len(failures), failures
    finally:
        generator.end_root()


def _publish_symbol_headers(
    options: GenerationOptions,
    config: Config,
    generator: DwarfGenerator,
    symbol_set: SymbolExtractionResult,
    identity_catalog: SourceIdentityCatalog,
) -> tuple[SymbolPublisher, str, Path]:
    publisher = SymbolPublisher(assembler=_implementation_assembler(options))
    source_sha256 = identity_catalog.sha256(config.elf_file_path)
    target = publisher.publish(
        config.output_dir,
        generator.platform,
        config.elf_file_path,
        source_sha256,
        symbol_set,
        None,
        emit_assembly=False,
        emit_sources=False,
        generate_context=options.generate_context,
    )
    return publisher, source_sha256, target


_ROOT_GENERATION_STATUSES: dict[str, GenerationStatus] = {
    "success": "success",
    "partial": "partial",
    "blocked": "blocked",
    "unavailable": "unavailable",
    "failed": "failed",
}


def _symbol_generation_outcomes(
    symbols: list[str], symbol_set: SymbolExtractionResult
) -> tuple[tuple[GenerationOutcome, ...], list[tuple[str, str]]]:
    outcomes: list[GenerationOutcome] = []
    failures: list[tuple[str, str]] = []
    for symbol in symbols:
        status = _ROOT_GENERATION_STATUSES.get(symbol_set.root_statuses.get(symbol, ""), "failed")
        headers = tuple(
            sorted(
                path
                for path, classes in symbol_set.header_classes.items()
                if any(
                    symbol in symbol_set.class_origins.get(class_name, ()) for class_name in classes
                )
            )
        )
        outcomes.append(GenerationOutcome(symbol=symbol, status=status, headers=headers))
        if status != "success":
            failures.append((symbol, f"generation status is {status}"))
    return tuple(outcomes), failures


def _implementation_assembler(options: GenerationOptions) -> Path | None:
    """Resolve the explicit assembler or the SDK sibling of Orbis objdump."""
    if options.orbis_as is not None:
        return options.orbis_as
    if options.orbis_objdump is None:
        return None
    parent = options.orbis_objdump.parent
    for name in ("orbis-as.exe", "orbis-as"):
        candidate = parent / name
        if candidate.is_file():
            return candidate
    return None


def _run_knowledge_export(
    options: GenerationOptions,
    config: Config,
    generator: DwarfGenerator,
    symbols: list[str],
    logger: Logger,
    tool_exports: tuple[ToolExport, ...],
) -> tuple[int, list[tuple[str, str]]]:
    output_dir = options.export_knowledge
    if output_dir is None:
        raise ValueError("knowledge export output directory is required")
    outcomes: list[GenerationOutcome] = []
    failures: list[tuple[str, str]] = []
    for index, symbol_name in enumerate(symbols, 1):
        with bind_context(symbol=symbol_name, symbol_index=index, symbol_count=len(symbols)):
            root_started = False
            try:
                generator.begin_root(symbol_name)
                root_started = True
                facade = generator.facade
                if facade is None:
                    raise RuntimeError("generation facade is unavailable outside an open session")
                build_id = (
                    options.build_id or f"{generator.platform.value}-{config.elf_file_path.stem}"
                )
                facade.export_knowledge_graph(
                    symbol_name,
                    output_dir,
                    build_id,
                    orbis_objdump_path=options.orbis_objdump,
                    tool_exports=tool_exports,
                )
                outcomes.append(GenerationOutcome(symbol=symbol_name, status="success"))
            except (OSError, RuntimeError, ValueError) as error:
                _record_failure(symbol_name, error, failures, logger)
                outcomes.append(
                    GenerationOutcome(symbol=symbol_name, status="error", error=str(error))
                )
            finally:
                if root_started:
                    generator.end_root()
    log_event(
        logger,
        20 if not failures else 30,
        "generation_report",
        fields=GenerationReport(tuple(symbols), tuple(outcomes), not failures).to_dict(),
    )
    return len(symbols) - len(failures), failures


def _session_factory(
    options: GenerationOptions, elf_path: Path, selection_cache_path: Path
) -> DwarfSessionFactory:
    """Select the infrastructure session at the composition root."""
    if options.dwarf_store_manifest is None:
        return create_dwarf_session
    from .infrastructure.analytical import AnalyticalDwarfSession

    def create_store_session(_requested_path: Path) -> AnalyticalDwarfSession:
        return AnalyticalDwarfSession(
            options.dwarf_store_manifest,
            expected_source_path=elf_path,
            selection_cache_path=selection_cache_path,
        )

    return create_store_session


def _record_failure(
    symbol_name: str,
    error: Exception,
    failed_symbols: list[tuple[str, str]],
    logger: Logger,
) -> None:
    log_exception(logger, "symbol_failed", error, symbol=symbol_name)
    failed_symbols.append((symbol_name, str(error)))


def run_generation(options: GenerationOptions) -> int:
    """Run one typed generation or knowledge-export request."""
    logger = get_logger(__name__)
    run_id = uuid4().hex
    command = "export-knowledge" if options.export_knowledge else "generate"
    try:
        config = _load_config(options)
        LoggerSetup.initialize(config.log_dir, verbose=config.verbose)
        with bind_context(
            run_id=run_id,
            command=command,
            input_path=options.elf_file,
            output_path=options.output,
        ):
            config.ensure_output_dir()
            symbols = _read_symbols(options, logger)
            _validate_store_options(options)
            _validate_implementation_options(options)
            _log_options(options, config.elf_file_path, config.output_dir, symbols, logger)
            success_count, failed_symbols = _run_generation(options, config, symbols, logger)
            _log_summary(symbols, success_count, failed_symbols, logger)
            return 0 if not failed_symbols else 1
    except Exception as error:
        captured_stdout, captured_stderr = sys.stdout, sys.stderr
        try:
            log_exception(
                logger,
                "generation_failed",
                error,
                run_id=run_id,
                command=command,
                input_path=options.elf_file,
            )
        finally:
            sys.stdout, sys.stderr = captured_stdout, captured_stderr
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit("Use ddon-dwarf-reconstructor through its Typer CLI")

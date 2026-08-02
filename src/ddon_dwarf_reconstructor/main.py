"""Generation workflow used by the typed command-line boundary."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .application.generators import DwarfGenerator, GenerationRequest
from .core.observability import bind_context, get_logger, log_event, log_exception
from .core.platform import ELFPlatform
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.composition import (
    create_disassembly_producer,
    create_dump_lookup,
    create_dwarf_session,
)
from .infrastructure.config import Config, DwarfRuntimeConfig, get_cache_file_path
from .infrastructure.header_output import AtomicHeaderPublisher
from .infrastructure.logging import LoggerSetup


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Typed options accepted by the generation and knowledge-export commands."""

    elf_file: Path
    symbols: tuple[str, ...] = ()
    symbols_file: Path | None = None
    output: Path | None = None
    verbose: bool = False
    full_hierarchy: bool = False
    single_file: bool = False
    exhaustive: bool = False
    dwarf_dump: Path | None = None
    dwarf_index: Path | None = None
    export_knowledge: Path | None = None
    build_id: str | None = None
    orbis_objdump: Path | None = None
    resolve_param_names: bool = False


def _load_config(options: GenerationOptions) -> Config:
    config = Config.from_args(
        elf_file_path=options.elf_file,
        output_dir=options.output,
        verbose=options.verbose,
    )
    config.validate()
    return config


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
    return symbols


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


def _log_options(
    options: GenerationOptions, config: Config, symbols: list[str], logger: Logger
) -> None:
    generation_mode = _generation_mode(options)
    search_mode = "exhaustive" if options.exhaustive else "fast (early-exit)"
    log_event(
        logger,
        20,
        "generation_options",
        symbol_count=len(symbols),
        input_path=config.elf_file_path,
        output_path=config.output_dir,
        generation_mode=generation_mode,
        search_mode=search_mode,
        parameter_name_resolution=options.resolve_param_names,
        dwarf_dump=options.dwarf_dump,
        dwarf_index=options.dwarf_index,
        export_knowledge=options.export_knowledge,
    )


def _generation_mode(options: GenerationOptions) -> str:
    if not options.full_hierarchy:
        return "single-header"
    return "full-hierarchy (single-file)" if options.single_file else "full-hierarchy (multi-file)"


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
    success_count = 0
    failed_symbols: list[tuple[str, str]] = []
    pending_headers: dict[str, str] = {}
    dwarf_config = DwarfRuntimeConfig.from_environment()
    identity_catalog = SourceIdentityCatalog()
    with DwarfGenerator(
        config.elf_file_path,
        session_factory=create_dwarf_session,
        exhaustive_search=options.exhaustive,
        dwarf_dump_path=options.dwarf_dump,
        dwarf_index_path=options.dwarf_index,
        resolve_param_names=options.resolve_param_names,
        dump_lookup_factory=create_dump_lookup,
        disassembly_factory=create_disassembly_producer,
        cache_file=get_cache_file_path(str(config.elf_file_path)),
        die_cache_size=dwarf_config.die_cache_size,
        type_cache_size=dwarf_config.type_cache_size,
        search_timeout=dwarf_config.search_timeout_seconds,
        source_hash=identity_catalog.sha256,
        source_identity=identity_catalog,
    ) as generator:
        for index, symbol_name in enumerate(symbols, 1):
            with bind_context(symbol=symbol_name, symbol_index=index, symbol_count=len(symbols)):
                started_at = perf_counter()
                log_event(logger, 20, "symbol_started", symbol=symbol_name)
                try:
                    if options.export_knowledge:
                        _process_symbol(options, config, generator, symbol_name, symbols, logger)
                    else:
                        pending_headers.update(_build_headers(options, generator, symbol_name))
                        if generator.lazy_index is not None:
                            generator.lazy_index.save_cache()
                    success_count += 1
                    log_event(
                        logger,
                        20,
                        "symbol_completed",
                        symbol=symbol_name,
                        duration_ms=round((perf_counter() - started_at) * 1000, 3),
                    )
                except (OSError, RuntimeError, ValueError) as error:
                    _record_failure(symbol_name, error, failed_symbols, logger)
        if pending_headers:
            total_bytes = _write_headers(config, generator, pending_headers, logger)
            _log_header_summary(options, generator, pending_headers, total_bytes, symbols, logger)
    return success_count, failed_symbols


def _process_symbol(
    options: GenerationOptions,
    config: Config,
    generator: DwarfGenerator,
    symbol_name: str,
    symbols: list[str],
    logger: Logger,
) -> None:
    if options.export_knowledge:
        build_id = options.build_id or f"{generator.platform.value}-{config.elf_file_path.stem}"
        generator.export_knowledge_graph(
            symbol_name,
            options.export_knowledge,
            build_id,
            orbis_objdump_path=options.orbis_objdump,
        )
        return
    headers = _build_headers(options, generator, symbol_name)
    total_bytes = _write_headers(config, generator, headers, logger)
    if generator.lazy_index is not None:
        generator.lazy_index.save_cache()
    _log_header_summary(options, generator, headers, total_bytes, symbols, logger)


def _build_headers(
    options: GenerationOptions, generator: DwarfGenerator, symbol_name: str
) -> dict[str, str]:
    request = GenerationRequest(
        symbol=symbol_name,
        full_hierarchy=options.full_hierarchy,
        single_file=options.single_file,
    )
    return dict(generator.generate_bundle(request).headers)


def _write_headers(
    config: Config, generator: DwarfGenerator, headers: dict[str, str], logger: Logger
) -> int:
    platform = getattr(generator, "platform", None)
    output_platform = platform if isinstance(platform, ELFPlatform) else ELFPlatform.UNKNOWN
    platform_dir, total_bytes = AtomicHeaderPublisher().publish(
        config.output_dir, output_platform, headers
    )
    filenames = sorted(headers)
    log_event(
        logger,
        20,
        "headers_published",
        output_dir=platform_dir,
        header_count=len(headers),
        total_bytes=total_bytes,
        sample_files=filenames[:10],
        sample_truncated=len(filenames) > 10,
    )
    return total_bytes


def _log_header_summary(
    options: GenerationOptions,
    generator: DwarfGenerator,
    headers: dict[str, str],
    total_bytes: int,
    symbols: list[str],
    logger: Logger,
) -> None:
    if options.full_hierarchy and not options.single_file:
        log_event(
            logger,
            10,
            "header_bundle_summary",
            header_count=len(headers),
            total_bytes=total_bytes,
            files=sorted(headers)[:20] if options.verbose else None,
        )
        return
    filename = next(iter(headers), "")
    lines = headers[filename].split("\n") if filename else []
    log_event(
        logger,
        10,
        "header_summary",
        filename=filename,
        line_count=len(lines),
        preview=lines[:30] if options.verbose and len(symbols) == 1 else None,
        preview_truncated=len(lines) > 30 if options.verbose and len(symbols) == 1 else False,
    )


def _record_failure(
    symbol_name: str,
    error: Exception,
    failed_symbols: list[tuple[str, str]],
    logger: Logger,
) -> None:
    log_exception(logger, "symbol_failed", error, symbol=symbol_name)
    failed_symbols.append((symbol_name, str(error)))


def _log_summary(
    symbols: list[str],
    success_count: int,
    failed_symbols: list[tuple[str, str]],
    logger: Logger,
) -> None:
    log_event(
        logger,
        20 if not failed_symbols else 30,
        "generation_summary",
        total_symbols=len(symbols),
        succeeded=success_count,
        failed=len(failed_symbols),
        failures=[{"symbol": symbol, "error": error} for symbol, error in failed_symbols[:20]],
        failures_truncated=len(failed_symbols) > 20,
    )


def run_generation(options: GenerationOptions) -> int:
    """Run one typed generation or knowledge-export request."""
    logger = get_logger(__name__)
    run_id = uuid4().hex
    command = "export-knowledge" if options.export_knowledge else "generate"
    try:
        LoggerSetup.initialize(Path("logs"), verbose=options.verbose)
        with bind_context(
            run_id=run_id,
            command=command,
            input_path=options.elf_file,
            output_path=options.output,
        ):
            config = _load_config(options)
            LoggerSetup.initialize(config.log_dir, verbose=config.verbose)
            config.ensure_output_dir()
            symbols = _read_symbols(options, logger)
            _log_options(options, config, symbols, logger)
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

"""Generation workflow used by the typed command-line boundary."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from logging import Logger
from pathlib import Path

from .application.generators import DwarfGenerator, GenerationRequest
from .core.observability import get_logger, log_timing
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.composition import create_disassembly_producer, create_dump_lookup
from .infrastructure.config import Config, get_cache_file_path, get_config
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
        logger.info("Read %s symbols from %s", len(symbols), path)
        return symbols
    except FileNotFoundError as error:
        raise ValueError(f"Symbols file not found: {path}") from error
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Error reading symbols file: {error}") from error


def _log_options(
    options: GenerationOptions, config: Config, symbols: list[str], logger: Logger
) -> None:
    logger.info("Generating headers for %s symbol(s)", len(symbols))
    generation_mode = _generation_mode(options)
    search_mode = "exhaustive" if options.exhaustive else "fast (early-exit)"
    parameter_mode = (
        "enabled (searching implementations)"
        if options.resolve_param_names
        else "disabled (auto-increment)"
    )
    logger.debug("ELF file: %s", config.elf_file_path)
    logger.debug("Output directory: %s", config.output_dir)
    logger.debug("Generation mode: %s", generation_mode)
    logger.debug("Search mode: %s", search_mode)
    logger.debug("Parameter name resolution: %s", parameter_mode)
    if options.dwarf_dump:
        logger.debug("DWARF dump: %s", options.dwarf_dump)
    if options.dwarf_index:
        logger.debug("DWARF index: %s", options.dwarf_index)


def _generation_mode(options: GenerationOptions) -> str:
    if not options.full_hierarchy:
        return "single-header"
    return (
        "full-hierarchy (single-file, legacy)"
        if options.single_file
        else "full-hierarchy (multi-file)"
    )


def _run_generation(
    options: GenerationOptions, config: Config, symbols: list[str], logger: Logger
) -> tuple[int, list[tuple[str, str]]]:
    success_count = 0
    failed_symbols: list[tuple[str, str]] = []
    try:
        dwarf_config = get_config()
        with DwarfGenerator(
            config.elf_file_path,
            exhaustive_search=options.exhaustive,
            dwarf_dump_path=options.dwarf_dump,
            dwarf_index_path=options.dwarf_index,
            resolve_param_names=options.resolve_param_names,
            dump_lookup_factory=create_dump_lookup,
            disassembly_factory=create_disassembly_producer,
            cache_file=get_cache_file_path(str(config.elf_file_path)),
            die_cache_size=int(dwarf_config["DIE_CACHE_SIZE"]),
            type_cache_size=int(dwarf_config["TYPE_CACHE_SIZE"]),
            source_hash=SourceIdentityCatalog().sha256,
        ) as generator:
            for index, symbol_name in enumerate(symbols, 1):
                logger.info("[%s/%s] Processing: %s", index, len(symbols), symbol_name)
                try:
                    _process_symbol(options, config, generator, symbol_name, symbols, logger)
                    success_count += 1
                except (OSError, RuntimeError, ValueError) as error:
                    _record_failure(symbol_name, error, failed_symbols, logger, config.verbose)
    except Exception as error:
        logger.error("Fatal error during generation: %s", error)
        _print_traceback(config.verbose)
        raise RuntimeError(f"Fatal error during generation: {error}") from error
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
    return generator.generate_bundle(request).as_dict()


def _write_headers(
    config: Config, generator: DwarfGenerator, headers: dict[str, str], logger: Logger
) -> int:
    platform = getattr(generator, "platform", None)
    platform_str = platform.value if platform is not None else "unknown"
    platform_dir = config.output_dir / platform_str
    platform_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for filename, content in headers.items():
        output_file = platform_dir / filename
        output_file.write_text(content, encoding="utf-8")
        total_bytes += len(content)
        logger.info("[SUCCESS] Generated: %s", output_file)
        logger.info("Size: %s bytes", len(content))
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
        logger.debug("Generated %s headers, %s total bytes", len(headers), total_bytes)
        if options.verbose:
            for filename in sorted(headers):
                logger.debug("  - %s", filename)
        return
    filename = next(iter(headers), "")
    lines = headers[filename].split("\n") if filename else []
    logger.debug("Generated header contains %s lines", len(lines))
    if options.verbose and len(symbols) == 1:
        logger.debug("\nPreview (first 30 lines):")
        for line in lines[:30]:
            logger.debug(line)
        if len(lines) > 30:
            logger.debug("... and %s more lines", len(lines) - 30)


def _record_failure(
    symbol_name: str,
    error: Exception,
    failed_symbols: list[tuple[str, str]],
    logger: Logger,
    verbose: bool,
) -> None:
    logger.error("[FAILED] %s: %s", symbol_name, error)
    failed_symbols.append((symbol_name, str(error)))
    if verbose:
        _print_traceback(True)


def _print_traceback(enabled: bool) -> None:
    if not enabled:
        return
    import traceback

    traceback.print_exc()


def _log_summary(
    symbols: list[str],
    success_count: int,
    failed_symbols: list[tuple[str, str]],
    logger: Logger,
) -> None:
    logger.info("=" * 70)
    logger.info("GENERATION SUMMARY")
    logger.info("=" * 70)
    logger.info("Total symbols: %s", len(symbols))
    logger.info("Successfully generated: %s", success_count)
    logger.info("Failed: %s", len(failed_symbols))
    if failed_symbols:
        logger.info("\nFailed symbols:")
        for symbol_name, error in failed_symbols:
            logger.info("  - %s: %s", symbol_name, error)


@log_timing
def run_generation(options: GenerationOptions) -> int:
    """Run one typed generation or knowledge-export request."""
    logger = get_logger(__name__)
    try:
        config = _load_config(options)
        LoggerSetup.initialize(config.log_dir, verbose=config.verbose)
        logger = get_logger(__name__)
        config.ensure_output_dir()
        symbols = _read_symbols(options, logger)
        _log_options(options, config, symbols, logger)
        success_count, failed_symbols = _run_generation(options, config, symbols, logger)
        _log_summary(symbols, success_count, failed_symbols, logger)
        return 0 if not failed_symbols else 1
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1


def main(options: GenerationOptions) -> int:
    """Compatibility façade for callers that invoke the generation workflow directly."""
    return run_generation(options)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit("Use ddon-dwarf-reconstructor through its Typer CLI")

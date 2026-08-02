"""Canonical command-line entry point for the DDON DWARF reconstructor."""

from __future__ import annotations

import sys
from argparse import Namespace
from logging import Logger
from pathlib import Path
from typing import NoReturn

from .application.generators import DwarfGenerator, GenerationRequest
from .cli_arguments import parse_args
from .infrastructure.composition import create_disassembly_producer, create_dump_lookup
from .infrastructure.config import Config
from .infrastructure.logging import LoggerSetup, get_logger, log_timing


def _load_config(args: Namespace) -> Config:
    try:
        config = Config.from_args(
            elf_file_path=args.elf_file,
            output_dir=args.output,
            verbose=args.verbose,
        )
        config.validate()
        return config
    except Exception as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def _read_symbols(args: Namespace, logger: Logger) -> list[str]:
    if args.generate and args.symbols_file:
        logger.error("Cannot use both --generate and --symbols-file options")
        raise SystemExit(1)
    if args.generate:
        symbols = [symbol.strip() for symbol in args.generate.split(",") if symbol.strip()]
    elif args.symbols_file:
        symbols = _read_symbol_file(args.symbols_file, logger)
    else:
        logger.error("Must provide either --generate or --symbols-file option")
        raise SystemExit(1)
    if not symbols:
        logger.error("No symbols provided")
        raise SystemExit(1)
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
        logger.error("Symbols file not found: %s", path)
        raise SystemExit(1) from error
    except (OSError, UnicodeError) as error:
        logger.error("Error reading symbols file: %s", error)
        raise SystemExit(1) from error


def _log_options(args: Namespace, config: Config, symbols: list[str], logger: Logger) -> None:
    logger.info("Generating headers for %s symbol(s)", len(symbols))
    generation_mode = _generation_mode(args)
    search_mode = "exhaustive" if args.exhaustive else "fast (early-exit)"
    parameter_mode = (
        "enabled (searching implementations)"
        if args.resolve_param_names
        else "disabled (auto-increment)"
    )
    logger.debug("ELF file: %s", config.elf_file_path)
    logger.debug("Output directory: %s", config.output_dir)
    logger.debug("Generation mode: %s", generation_mode)
    logger.debug("Search mode: %s", search_mode)
    logger.debug("Parameter name resolution: %s", parameter_mode)
    if args.dwarf_dump:
        logger.debug("DWARF dump: %s", args.dwarf_dump)
    if args.dwarf_index:
        logger.debug("DWARF index: %s", args.dwarf_index)


def _generation_mode(args: Namespace) -> str:
    if not args.full_hierarchy:
        return "single-header"
    return (
        "full-hierarchy (single-file, legacy)"
        if args.single_file
        else "full-hierarchy (multi-file)"
    )


def _run_generation(
    args: Namespace, config: Config, symbols: list[str], logger: Logger
) -> tuple[int, list[tuple[str, str]]]:
    success_count = 0
    failed_symbols: list[tuple[str, str]] = []
    try:
        with DwarfGenerator(
            config.elf_file_path,
            exhaustive_search=args.exhaustive,
            dwarf_dump_path=args.dwarf_dump,
            dwarf_index_path=args.dwarf_index,
            resolve_param_names=args.resolve_param_names,
            dump_lookup_factory=create_dump_lookup,
            disassembly_factory=create_disassembly_producer,
        ) as generator:
            for index, symbol_name in enumerate(symbols, 1):
                logger.info("[%s/%s] Processing: %s", index, len(symbols), symbol_name)
                try:
                    _process_symbol(args, config, generator, symbol_name, symbols, logger)
                    success_count += 1
                except (OSError, RuntimeError, ValueError) as error:
                    _record_failure(symbol_name, error, failed_symbols, logger, config.verbose)
    except Exception as error:
        logger.error("Fatal error during generation: %s", error)
        _print_traceback(config.verbose)
        raise SystemExit(1) from error
    return success_count, failed_symbols


def _process_symbol(
    args: Namespace,
    config: Config,
    generator: DwarfGenerator,
    symbol_name: str,
    symbols: list[str],
    logger: Logger,
) -> None:
    if args.export_knowledge:
        build_id = args.build_id or f"{generator.platform.value}-{config.elf_file_path.stem}"
        generator.export_knowledge_graph(
            symbol_name, args.export_knowledge, build_id, orbis_objdump_path=args.orbis_objdump
        )
        return
    headers = _build_headers(args, generator, symbol_name)
    total_bytes = _write_headers(config, generator, headers, logger)
    if generator.lazy_index is not None:
        generator.lazy_index.save_cache()
    _log_header_summary(args, generator, headers, total_bytes, symbols, logger)


def _build_headers(args: Namespace, generator: DwarfGenerator, symbol_name: str) -> dict[str, str]:
    request = GenerationRequest(
        symbol=symbol_name,
        full_hierarchy=args.full_hierarchy,
        single_file=args.single_file,
    )
    return generator.generate_bundle(request).as_dict()


def _write_headers(
    config: Config, generator: DwarfGenerator, headers: dict[str, str], logger: Logger
) -> int:
    platform_str = generator.platform.value if generator.platform else "unknown"
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
    args: Namespace,
    generator: DwarfGenerator,
    headers: dict[str, str],
    total_bytes: int,
    symbols: list[str],
    logger: Logger,
) -> None:
    if args.full_hierarchy and not args.single_file:
        logger.debug("Generated %s headers, %s total bytes", len(headers), total_bytes)
        if args.verbose:
            for filename in sorted(headers):
                logger.debug("  - %s", filename)
        return
    filename = next(iter(headers), "")
    lines = headers[filename].split("\n") if filename else []
    logger.debug("Generated header contains %s lines", len(lines))
    if args.verbose and len(symbols) == 1:
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
def main() -> NoReturn:
    """Run the canonical DWARF-to-header workflow."""
    logger = get_logger(__name__)
    args = parse_args()
    config = _load_config(args)
    LoggerSetup.initialize(Path("logs"), verbose=config.verbose)
    logger = get_logger(__name__)
    config.ensure_output_dir()
    symbols = _read_symbols(args, logger)
    _log_options(args, config, symbols, logger)
    success_count, failed_symbols = _run_generation(args, config, symbols, logger)
    _log_summary(symbols, success_count, failed_symbols, logger)
    raise SystemExit(0 if not failed_symbols else 1)


if __name__ == "__main__":
    main()

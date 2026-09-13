"""Logging helpers for the command-level generation workflow."""

from __future__ import annotations

from collections.abc import Sequence
from logging import Logger
from pathlib import Path

from ...core.observability import log_event
from .options import GenerationOptions


def log_generation_options(
    options: GenerationOptions,
    input_path: Path,
    output_path: Path,
    symbols: Sequence[str],
    logger: Logger,
) -> None:
    """Emit the bounded configuration record for a generation request."""
    log_event(
        logger,
        20,
        "generation_options",
        symbol_count=len(symbols),
        input_path=input_path,
        output_path=output_path,
        generation_mode=generation_mode(options),
        generate_context=options.generate_context,
        search_mode="exhaustive" if options.exhaustive else "fast (early-exit)",
        parameter_name_resolution=options.resolve_param_names,
        dwarf_dump=options.dwarf_dump,
        dwarf_index=options.dwarf_index,
        dwarf_store_manifest=options.dwarf_store_manifest,
        export_knowledge=options.export_knowledge,
        extract_assembly=options.extract_assembly,
        emit_implementation_sources=options.emit_implementation_sources,
        orbis_objdump=options.orbis_objdump,
        orbis_as=options.orbis_as,
        llvm_readobj=options.llvm_readobj,
        llvm_objdump=options.llvm_objdump,
        llvm_target_triple=options.llvm_target_triple,
        tool_export_manifest_count=len(options.tool_export_manifests),
        tool_export_manifests=options.tool_export_manifests,
    )


def generation_mode(options: GenerationOptions) -> str:
    if not options.export_knowledge:
        return "symbol-set"
    if not options.full_hierarchy:
        return "single-header"
    return "full-hierarchy (single-file)" if options.single_file else "full-hierarchy (multi-file)"


def log_generation_summary(
    symbols: Sequence[str],
    success_count: int,
    failed_symbols: Sequence[tuple[str, str]],
    logger: Logger,
) -> None:
    """Emit the bounded end-of-run summary for header generation."""
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


__all__ = ["generation_mode", "log_generation_options", "log_generation_summary"]

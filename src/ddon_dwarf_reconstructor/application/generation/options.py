"""Typed request options shared by the CLI and generation application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    dwarf_store_manifest: Path | None = None
    export_knowledge: Path | None = None
    build_id: str | None = None
    orbis_objdump: Path | None = None
    resolve_param_names: bool = False
    tool_export_manifests: tuple[Path, ...] = ()


__all__ = ["GenerationOptions"]

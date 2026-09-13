"""Typed request options shared by the CLI and generation application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_LLVM_TARGET_TRIPLE = "x86_64-scei-ps4"


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Typed options accepted by the generation and knowledge-export commands."""

    elf_file: Path
    symbols: tuple[str, ...] = ()
    symbols_file: Path | None = None
    output: Path | None = None
    verbose: bool = False
    generate_context: bool = True
    full_hierarchy: bool = False
    single_file: bool = False
    exhaustive: bool = False
    dwarf_dump: Path | None = None
    dwarf_index: Path | None = None
    dwarf_store_manifest: Path | None = None
    export_knowledge: Path | None = None
    build_id: str | None = None
    orbis_objdump: Path | None = None
    orbis_as: Path | None = None
    llvm_readobj: Path | None = None
    llvm_objdump: Path | None = None
    llvm_target_triple: str = DEFAULT_LLVM_TARGET_TRIPLE
    extract_assembly: bool = False
    emit_implementation_sources: bool = False
    resolve_param_names: bool = False
    tool_export_manifests: tuple[Path, ...] = ()


def validate_implementation_options(options: GenerationOptions) -> None:
    """Reject profile combinations whose evidence chain would ignore them."""
    if options.export_knowledge is None and options.single_file:
        raise ValueError(
            "--single-file is not supported for symbol generation; the complete dependency "
            "closure is always published as flat files"
        )
    if options.emit_implementation_sources and not options.extract_assembly:
        raise ValueError("--emit-implementation-sources requires --extract-assembly")
    _validate_profile_option(options, options.orbis_objdump, "--orbis-objdump")
    _validate_profile_option(options, options.orbis_as, "--orbis-as")
    _validate_profile_option(options, options.llvm_objdump, "--llvm-objdump")
    _validate_profile_option(options, options.llvm_readobj, "--llvm-readobj")
    if _has_llvm_without_orbis(options):
        raise ValueError(
            "--llvm-readobj/--llvm-objdump require --orbis-objdump because LLVM evidence "
            "is an additive cross-check"
        )
    if options.llvm_objdump is None and options.llvm_target_triple != DEFAULT_LLVM_TARGET_TRIPLE:
        raise ValueError("--llvm-target-triple requires --llvm-objdump")


def _validate_profile_option(
    options: GenerationOptions, executable: Path | None, option_name: str
) -> None:
    if executable is not None and not options.extract_assembly and options.export_knowledge is None:
        raise ValueError(f"{option_name} requires --extract-assembly")


def _has_llvm_without_orbis(options: GenerationOptions) -> bool:
    return (
        (options.llvm_objdump is not None or options.llvm_readobj is not None)
        and options.orbis_objdump is None
        and (options.extract_assembly or options.export_knowledge is not None)
    )


__all__ = ["DEFAULT_LLVM_TARGET_TRIPLE", "GenerationOptions", "validate_implementation_options"]

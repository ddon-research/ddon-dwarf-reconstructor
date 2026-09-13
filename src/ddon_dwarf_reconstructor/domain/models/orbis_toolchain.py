"""Typed contracts for the reviewed Orbis compiler and host-tool profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class OrbisToolchainContract:
    """Versioned facts observed from one local Orbis SDK toolchain."""

    profile_id: str
    sdk_version: str
    clang_version: str
    assembler_version: str
    linker_version: str
    llvm_mca_version: str
    target_triple: str
    bfd_target: str
    configure_triple: str
    assembler_syntax: str
    integrated_assembler_default: bool
    compiler_defaults: tuple[str, ...]
    abi_rules: tuple[str, ...]
    elf_rules: tuple[str, ...]
    elf_flags: tuple[str, ...]
    relocation_definitions: tuple[str, ...]
    documentation_sources: tuple[str, ...]
    status: str = "observed"
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, object]:
        """Return stable JSON-compatible contract data."""
        return asdict(self)


__all__ = ["OrbisToolchainContract"]

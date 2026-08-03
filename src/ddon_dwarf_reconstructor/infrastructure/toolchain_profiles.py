"""Explicit external-tool export profiles and their authority boundaries."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_EXPORT_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ToolExportProfile:
    """A bounded command recipe for one external evidence source."""

    name: str
    tool_name: str
    arguments: tuple[str, ...]
    output_format: str
    authority: str
    description: str
    max_output_bytes: int = DEFAULT_MAX_EXPORT_BYTES


_PROFILES = (
    ToolExportProfile(
        name="elfutils-elflint",
        tool_name="eu-elflint",
        arguments=("--gnu-ld",),
        output_format="text",
        authority="generic_elf_cross_check",
        description="elfutils structural validation; interpret SCE extensions separately.",
    ),
    ToolExportProfile(
        name="gnu-elf-headers",
        tool_name="readelf",
        arguments=("-h", "-l", "-S", "-r"),
        output_format="text",
        authority="generic_elf_cross_check",
        description="GNU ELF headers, sections, and relocation cross-check output.",
    ),
    ToolExportProfile(
        name="gnu-symbols",
        tool_name="nm",
        arguments=("-C", "-n", "-S", "--defined-only"),
        output_format="text",
        authority="generic_symbol_cross_check",
        description="GNU demangled, address-sorted defined-symbol cross-check output.",
    ),
    ToolExportProfile(
        name="libdwarf-producers",
        tool_name="dwarfdump",
        arguments=("--print-producers",),
        output_format="text",
        authority="dwarf_cross_check",
        description="libdwarf producer strings and compilation-unit provenance.",
    ),
    ToolExportProfile(
        name="libdwarf-check-summary",
        tool_name="dwarfdump",
        arguments=("--check-summary",),
        output_format="text",
        authority="dwarf_cross_check",
        description="Bounded libdwarf integrity summary for references and ranges.",
    ),
    ToolExportProfile(
        name="orbis-elf-headers",
        tool_name="orbis-readelf",
        arguments=("-h", "-l"),
        output_format="text",
        authority="ps4_abi_authority",
        description="PS4 ELF and SCE program-header evidence from the matching Orbis SDK.",
    ),
    ToolExportProfile(
        name="orbis-symbols",
        tool_name="orbis-nm",
        arguments=("-C", "-n", "-S", "--defined-only"),
        output_format="text",
        authority="ps4_symbol_authority",
        description="Demangled, address-sorted defined symbols from the Orbis BFD target.",
    ),
    ToolExportProfile(
        name="llvm-elf-metadata-json",
        tool_name="llvm-readelf",
        arguments=(
            "--elf-output-style=JSON",
            "--file-header",
            "--program-headers",
            "--sections",
        ),
        output_format="json",
        authority="generic_elf_cross_check",
        description="Machine-readable standard ELF metadata; SCE values remain additive only.",
    ),
    ToolExportProfile(
        name="llvm-debug-info-summary",
        tool_name="llvm-debuginfo-analyzer",
        arguments=("--print=summary",),
        output_format="text",
        authority="dwarf_cross_check",
        description="LLVM debug-info summary for bounded producer and scope comparison.",
    ),
    ToolExportProfile(
        name="llvm-dwarf-statistics",
        tool_name="llvm-dwarfdump",
        arguments=("--statistics",),
        output_format="jsonl",
        authority="dwarf_cross_check",
        description="LLVM DWARF quality statistics emitted as machine-readable JSON.",
    ),
    ToolExportProfile(
        name="libdwarf-check-all",
        tool_name="dwarfdump",
        arguments=("--check-all",),
        output_format="text",
        authority="dwarf_cross_check",
        description=(
            "Full libdwarf integrity checks with a bounded output cap; oversized output fails closed."
        ),
        max_output_bytes=64 * 1024 * 1024,
    ),
)

PROFILES = {profile.name: profile for profile in _PROFILES}


def get_tool_export_profile(name: str) -> ToolExportProfile:
    """Return one named profile or a useful error listing the available profiles."""
    try:
        return PROFILES[name]
    except KeyError as error:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown tool export profile {name!r}; choose from {available}"
        ) from error


def list_tool_export_profiles() -> tuple[ToolExportProfile, ...]:
    """Return profiles in deterministic name order for CLI and documentation."""
    return tuple(PROFILES[name] for name in sorted(PROFILES))

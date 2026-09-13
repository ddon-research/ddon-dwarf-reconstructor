"""Application-facing execution helper for the implementation validator."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .implementation_validation import resolve_sdk_tool, validate_implementation
from .implementation_validation_summary import implementation_validation_summary
from .orbis_toolchain_contracts import select_toolchain_profile


def execute_implementation_validation(
    elf: Path,
    implementation_report: Path,
    output_dir: Path,
    *,
    load_base: str | None,
    original_addresses: bool,
    dwarf_store: Path | None,
    nid_database: Path | None,
    nid_database_provenance: Path | None = None,
    sdk_root: Path | None,
    orbis_as: Path | None,
    orbis_clang: Path | None,
    orbis_readelf: Path | None,
    orbis_objdump: Path | None,
    orbis_ld: Path | None,
    write_result: Callable[[dict[str, Any]], None],
    tool_evidence: tuple[Path, ...] = (),
    abi_probe_manifest: Path | None = None,
    tool_timeout_seconds: float | None = None,
    assembly_profile: str = "byte-replay",
) -> None:
    """Resolve tools, run validation, and emit only its bounded CLI projection."""
    parsed_base = int(load_base, 0) if load_base is not None else None
    assembler = orbis_as or resolve_sdk_tool(sdk_root, "orbis-as")
    compiler = orbis_clang or resolve_sdk_tool(sdk_root, "orbis-clang++")
    readelf = orbis_readelf or resolve_sdk_tool(sdk_root, "orbis-readelf")
    objdump = orbis_objdump or resolve_sdk_tool(sdk_root, "orbis-objdump")
    linker = orbis_ld or resolve_sdk_tool(sdk_root, "orbis-ld")
    toolchain_profile, profile_diagnostics = select_toolchain_profile(
        sdk_root,
        tuple(path for path in (assembler, compiler, readelf, objdump, linker) if path is not None),
    )
    report = validate_implementation(
        elf,
        implementation_report,
        output_dir,
        load_base=parsed_base,
        original_addresses=original_addresses,
        dwarf_store=dwarf_store,
        nid_database=nid_database,
        nid_database_provenance=nid_database_provenance,
        orbis_as=assembler,
        orbis_clang=compiler,
        orbis_readelf=readelf,
        orbis_objdump=objdump,
        orbis_ld=linker,
        tool_evidence=tool_evidence,
        abi_probe_manifest=abi_probe_manifest,
        toolchain_profile=toolchain_profile,
        toolchain_diagnostics=profile_diagnostics,
        tool_timeout_seconds=tool_timeout_seconds,
        assembly_profile=assembly_profile,
    )
    write_result(
        {
            "status": report.status.value,
            "validation_report_path": str(
                output_dir.resolve() / f"implementation-validation-{report.source_sha256[:16]}.json"
            ),
            "report": implementation_validation_summary(report),
        }
    )


__all__ = ["execute_implementation_validation"]

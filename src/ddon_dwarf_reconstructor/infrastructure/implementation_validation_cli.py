"""Application-facing execution helper for the implementation validator."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .implementation_validation import resolve_sdk_tool, validate_implementation
from .implementation_validation_summary import implementation_validation_summary


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
    tool_timeout_seconds: float | None = None,
) -> None:
    """Resolve tools, run validation, and emit only its bounded CLI projection."""
    parsed_base = int(load_base, 0) if load_base is not None else None
    assembler = orbis_as or resolve_sdk_tool(sdk_root, "orbis-as")
    compiler = orbis_clang or resolve_sdk_tool(sdk_root, "orbis-clang++")
    readelf = orbis_readelf or resolve_sdk_tool(sdk_root, "orbis-readelf")
    objdump = orbis_objdump or resolve_sdk_tool(sdk_root, "orbis-objdump")
    linker = orbis_ld or resolve_sdk_tool(sdk_root, "orbis-ld")
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
        tool_timeout_seconds=tool_timeout_seconds,
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

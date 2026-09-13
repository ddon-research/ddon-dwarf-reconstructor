"""Typed context passed through implementation-validation orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple


class ValidationRun(NamedTuple):
    source: Path
    implementation_report: Path
    output_dir: Path
    raw: dict[str, Any]
    source_sha256: str
    report_sha256: str
    diagnostics: list[str]
    load_base: int | None
    original_addresses: bool
    nid_database: Path | None
    nid_database_provenance: Path | None
    orbis_as: Path | None
    orbis_clang: Path | None
    orbis_readelf: Path | None
    orbis_objdump: Path | None
    orbis_ld: Path | None
    tool_evidence: tuple[Path, ...]
    abi_probe_manifest: Path | None
    toolchain_profile: str
    toolchain_diagnostics: tuple[str, ...]
    tool_timeout_seconds: float | None
    assembly_profile: str
    store: Any | None
    manifest_sha: str | None
    store_schema: str | None
    analytical_model: Any | None


__all__ = ["ValidationRun"]

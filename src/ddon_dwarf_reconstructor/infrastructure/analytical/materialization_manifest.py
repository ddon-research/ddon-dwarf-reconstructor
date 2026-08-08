"""Manifest builders for complete stores and explicit checkpoint snapshots."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationArtifact,
    MaterializationManifest,
)
from .dwarf_recovery import DwarfRecoveryReport


def build_manifest(
    request: DwarfMaterializationRequest,
    source_path: Path,
    identity: Any,
    platform: str,
    section_names: list[str],
    counts: Counter[str],
    cu_passes: int,
    has_parquet: bool,
    artifacts: tuple[MaterializationArtifact, ...] = (),
    writer_metrics: dict[str, int] | None = None,
    parse_error_count: int = 0,
    recovery: DwarfRecoveryReport | None = None,
) -> MaterializationManifest:
    """Build the source-bound manifest for one published materialization."""
    configuration = _configuration(request, cu_passes, parse_error_count, recovery)
    if writer_metrics:
        configuration["parquet_writer_metrics"] = writer_metrics
    return MaterializationManifest(
        schema_version=request.schema_version,
        source_path=str(source_path),
        source_identity=identity,
        producer=_producer(request, has_parquet, recovery),
        platform=platform,
        files=_files(request, has_parquet, "manifest.json"),
        counts=dict(sorted(counts.items())),
        configuration=configuration,
        section_names=tuple(section_names),
        artifacts=artifacts,
        status=_status(request, parse_error_count),
    )


def build_checkpoint_manifest(
    request: DwarfMaterializationRequest,
    source_path: Path,
    identity: Any,
    platform: str,
    section_names: list[str],
    counts: Counter[str],
    cu_passes: int,
    parquet_files: tuple[str, ...],
    artifacts: tuple[MaterializationArtifact, ...] = (),
    writer_metrics: dict[str, int] | None = None,
    parse_error_count: int = 0,
    recovery: DwarfRecoveryReport | None = None,
) -> MaterializationManifest:
    """Build an immutable, explicitly in-progress checkpoint manifest."""
    configuration = _configuration(request, cu_passes, parse_error_count, recovery)
    configuration.update(
        {
            "checkpoint": {"status": "in_progress", "cu_count": cu_passes},
            "parquet_files": list(parquet_files),
        }
    )
    if writer_metrics:
        configuration["parquet_writer_metrics"] = writer_metrics
    return MaterializationManifest(
        schema_version=request.schema_version,
        source_path=str(source_path),
        source_identity=identity,
        producer="pyelftools-0.33-one-pass-checkpoint",
        platform=platform,
        files=_files(request, True, "checkpoint.json"),
        counts=dict(sorted(counts.items())),
        configuration=configuration,
        section_names=tuple(section_names),
        artifacts=artifacts,
        status="in_progress",
    )


def _configuration(
    request: DwarfMaterializationRequest,
    cu_passes: int,
    parse_error_count: int,
    recovery: DwarfRecoveryReport | None,
) -> dict[str, Any]:
    configuration: dict[str, Any] = {
        "raw_chunk_size": request.raw_chunk_size,
        "cu_passes": cu_passes,
        "checkpoint_every_cus": request.checkpoint_every_cus,
        "write_jsonl": request.write_jsonl,
        "write_parquet": request.write_parquet,
        "max_cus": request.max_cus,
        "max_open_writers": request.max_open_writers,
        "parquet_layout": request.parquet_layout,
        "rotate_writers_every_cus": request.rotate_writers_every_cus,
        "parse_error_count": parse_error_count,
        "dwarf_parse_status": "partial" if parse_error_count else "complete",
    }
    if recovery is not None:
        configuration["dwarf_recovery"] = recovery.to_dict()
    return configuration


def _files(
    request: DwarfMaterializationRequest,
    has_parquet: bool,
    manifest_name: str,
) -> dict[str, str]:
    files = {
        "raw_sections": "raw_sections",
        "raw_values": "raw_values",
        "manifest": manifest_name,
    }
    if request.write_jsonl:
        files["records"] = "records.jsonl"
    if has_parquet:
        files["parquet"] = "parquet"
    return files


def _producer(
    request: DwarfMaterializationRequest,
    has_parquet: bool,
    recovery: DwarfRecoveryReport | None,
) -> str:
    producer = (
        "pyelftools-0.33-one-pass-direct"
        if has_parquet and not request.write_jsonl
        else "pyelftools-0.33-one-pass"
    )
    if recovery is not None and recovery.status in {"applied", "already_applied"}:
        producer += "-source-recovery"
    return producer


def _status(request: DwarfMaterializationRequest, parse_error_count: int) -> str:
    return "partial" if request.max_cus is not None or parse_error_count else "complete"

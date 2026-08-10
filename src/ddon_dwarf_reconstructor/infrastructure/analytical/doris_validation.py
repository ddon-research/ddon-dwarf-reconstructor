"""Source-bound validation for native Doris load plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .manifest import (
    declared_parquet_files,
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    validate_manifest_files,
)


def validate_manifest_for_load(manifest: Any, manifest_path: Path) -> None:
    if manifest.status != "complete":
        raise ValueError(f"Doris loading requires a complete analytical store: {manifest_path}")
    if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
        raise ValueError(f"Doris loading requires complete DWARF parsing: {manifest_path}")


def validate_plan_files(plan: Any, manifest_path: Path, manifest: Any) -> None:
    declared = declared_parquet_files(manifest_path, manifest)
    planned = tuple(path.resolve() for path in plan.parquet_files)
    if planned != declared:
        raise ValueError("Doris load plan does not match manifest Parquet files")


def validate_plan_settings(plan: Any, config: Any) -> None:
    if plan.database != config.database or plan.table != config.table:
        raise ValueError("Doris load plan does not match connection table settings")
    if (
        plan.statistics_policy != config.statistics_policy
        or plan.serving_variant_id != config.serving_variant_id
        or plan.stream_load_workers != config.stream_load_workers
    ):
        raise ValueError("Doris load plan does not match serving or statistics settings")


def validate_plan_manifest_files(manifest_path: Path, manifest: Any) -> None:
    validate_manifest_files(manifest_path, manifest, verify_hashes=True, verify_payload=True)

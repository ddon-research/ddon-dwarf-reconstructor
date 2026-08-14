"""Explicit file-backed analytical stores for inspection and migration tools."""

from __future__ import annotations

from pathlib import Path

from .jsonl_store import JsonlDwarfStore
from .manifest import load_manifest
from .materialized_views import MaterializedStorePort


def load_analytical_store(
    manifest_path: Path,
    *,
    verify_source: bool = True,
    source_path: Path | None = None,
    allow_incomplete: bool = False,
    verify_artifacts: bool = False,
    selection_cache_path: Path | None = None,
    selection_source_fingerprint: dict[str, int | str] | None = None,
) -> MaterializedStorePort:
    """Load a JSONL/Parquet artifact explicitly outside generation."""
    manifest = load_manifest(manifest_path.resolve())
    if "parquet" in manifest.files:
        from .parquet_store import ParquetDwarfStore

        return ParquetDwarfStore.load(
            manifest_path,
            verify_source=verify_source,
            source_path=source_path,
            allow_incomplete=allow_incomplete,
            verify_artifacts=verify_artifacts,
            selection_cache_path=selection_cache_path,
            selection_source_fingerprint=selection_source_fingerprint,
        )
    return JsonlDwarfStore.load(
        manifest_path,
        verify_source=verify_source,
        source_path=source_path,
        allow_incomplete=allow_incomplete,
        verify_artifacts=verify_artifacts,
        selection_cache_path=selection_cache_path,
        selection_source_fingerprint=selection_source_fingerprint,
    )

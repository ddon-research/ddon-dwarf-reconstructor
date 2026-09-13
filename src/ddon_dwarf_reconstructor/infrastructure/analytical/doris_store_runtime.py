"""Runtime row access and source-bound store validation helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from ...domain.models.analytical_dwarf import MaterializationManifest
from ..artifacts import SourceIdentityCatalog
from .doris_rows import restore_row
from .manifest import has_parser_diagnostics, has_unapplied_source_recovery, validate_schema_version


class DorisStoreRuntimeMixin:
    """Provide typed batch and compatibility row reads for the Doris store."""

    def _record_batches(
        self: _QueryBacked,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
        operation: str = "family_record_batches",
    ) -> tuple[Any, ...]:
        return self._queries.family_record_batches(
            family,
            filters,
            columns=columns,
            order_by=order_by,
            limit=limit,
            table_name=table_name,
            operation=operation,
        )

    def _rows(
        self: _QueryBacked,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
        operation: str = "family_rows",
    ) -> tuple[dict[str, Any], ...]:
        query_options: dict[str, Any] = {
            "columns": columns,
            "order_by": order_by,
            "limit": limit,
            "operation": operation,
        }
        if table_name is not None:
            query_options["table_name"] = table_name
        rows = self._queries.family_rows(family, filters, **query_options)
        return tuple(restore_row(dict(row)) for row in rows)


class _QueryBacked(Protocol):
    _queries: Any


def runtime_cache_size(name: str, default: int) -> int:
    """Read one positive bounded-cache setting without silently accepting bad input."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        size = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if size < 1:
        raise ValueError(f"{name} must be a positive integer")
    return size


def validate_runtime_manifest(manifest: MaterializationManifest, path: Path) -> None:
    validate_schema_version(manifest, allow_incomplete=False)
    if manifest.status != "complete":
        raise ValueError(f"Analytical store is not complete: {path}")
    if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
        raise ValueError(f"Analytical store has partial DWARF parsing: {path}")


def verify_source_binding(manifest: MaterializationManifest, source_path: Path | None) -> None:
    source = (source_path or Path(manifest.source_path)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Materialization source is unavailable: {source}")
    identity = SourceIdentityCatalog().identify(source)
    if identity.sha256 != manifest.source_identity.sha256:
        raise ValueError(f"Materialization source hash mismatch: {source}")


__all__ = [
    "DorisStoreRuntimeMixin",
    "runtime_cache_size",
    "validate_runtime_manifest",
    "verify_source_binding",
]

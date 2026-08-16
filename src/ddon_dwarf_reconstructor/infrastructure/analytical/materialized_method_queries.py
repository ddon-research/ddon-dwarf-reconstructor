"""Shared implementation-index projection for explicit file-backed adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...domain.models.analytical_dwarf import MaterializationManifest, QueryResult, QueryStatus
from .jsonl_views import StoreDie
from .materialized_selection import query_status as _query_status


def method_implementation_rows(
    manifest: MaterializationManifest,
    candidates_by_offset: Mapping[int, Sequence[StoreDie]],
    declaration_offsets: Sequence[int],
    *,
    provenance: str,
) -> QueryResult:
    """Return a deterministic bounded projection without changing query semantics."""
    offsets = tuple(sorted({offset for offset in declaration_offsets if isinstance(offset, int)}))
    rows: list[dict[str, Any]] = []
    for declaration_offset in offsets:
        for die in candidates_by_offset.get(declaration_offset, ()):
            rows.append(_row(manifest, declaration_offset, die))
    rows.sort(key=_row_sort_key)
    truncated = len(rows) > 100_000
    rows = rows[:100_000]
    diagnostics = ("method implementation batch reached its safety bound",) if truncated else ()
    return QueryResult(
        _query_status(bool(rows), manifest.status, truncated=truncated),
        tuple(rows),
        (provenance,),
        diagnostics,
        truncated,
    )


def _row(manifest: MaterializationManifest, target_offset: int, die: StoreDie) -> dict[str, Any]:
    attribute = die.attributes.get("DW_AT_name")
    return {
        "source_id": manifest.source_identity.sha256,
        "unit_offset": die.cu.cu_offset,
        "die_offset": die.offset,
        "index_type": "method_implementation",
        "name": getattr(attribute, "value", None),
        "tag": die.tag,
        "target_offset": target_offset,
        "resolution_status": QueryStatus.COMPLETE.value,
    }


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(row.get("target_offset", 0)),
        int(row.get("unit_offset", 0)),
        int(row.get("die_offset", 0)),
    )


__all__ = ["method_implementation_rows"]

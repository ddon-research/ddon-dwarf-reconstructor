"""Shared definition policy for JSONL and Parquet materialized adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.services.definition_selection import (
    DefinitionCandidate,
    DefinitionSignals,
    build_definition_candidate,
    definition_candidate_sort_key,
)
from .jsonl_views import StoreDie

DEFINITION_QUERY_LIMIT = 1000


def definition_matches(
    die: StoreDie,
    qualified_name: str | None,
    tags: frozenset[str] | None,
) -> bool:
    if tags is not None and die.tag not in tags:
        return False
    return qualified_name is None or die.get_full_path() == qualified_name


def definition_candidate(symbol_name: str, die: StoreDie) -> DefinitionCandidate:
    byte_size = _attribute_int(die, "DW_AT_byte_size") or 0
    return build_definition_candidate(
        symbol_name,
        cu_offset=die.cu.cu_offset,
        die_offset=die.offset,
        signals=DefinitionSignals(
            tag=str(die.tag),
            byte_size=byte_size,
            has_children=die.has_children,
            is_declaration="DW_AT_declaration" in die.attributes,
            has_type_reference="DW_AT_type" in die.attributes,
            nested=die.child_tag_counts(),
        ),
    )


def definition_sort_key(die: StoreDie) -> tuple[int, int, int, int]:
    candidate = definition_candidate("", die)
    return definition_candidate_sort_key(candidate, depth=die.depth)


def query_status(found: bool, manifest_status: str, *, truncated: bool = False) -> QueryStatus:
    if manifest_status != "complete" or truncated:
        return QueryStatus.PARTIAL
    return QueryStatus.COMPLETE if found else QueryStatus.NOT_FOUND


def result(
    item: Any,
    manifest_path: Path,
    manifest_status: str = "complete",
    *,
    truncated: bool = False,
) -> QueryResult:
    status = query_status(item is not None, manifest_status, truncated=truncated)
    diagnostics = ("query result reached its safety bound",) if truncated else ()
    return QueryResult(
        status,
        (item,) if item is not None else (),
        (str(manifest_path),),
        diagnostics,
        truncated,
    )


def unavailable(error: Exception, manifest_path: Path) -> QueryResult:
    """Preserve projection read failures as explicit non-complete evidence."""
    text = f"materialized query unavailable: {error}"
    suffix = "...[truncated]"
    diagnostic = text if len(text) <= 2048 else text[: 2048 - len(suffix)] + suffix
    return QueryResult(
        QueryStatus.UNAVAILABLE,
        provenance=(str(manifest_path),),
        diagnostics=(diagnostic,),
    )


def _attribute_int(die: StoreDie, name: str) -> int | None:
    value = die.attributes.get(name)
    return value.value if value is not None and isinstance(value.value, int) else None

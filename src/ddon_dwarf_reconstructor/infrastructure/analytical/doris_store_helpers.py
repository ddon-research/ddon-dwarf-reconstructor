"""Small value helpers shared by the Doris store query façade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from .doris_models import DorisDie


def definition_matches(
    die: DorisDie,
    qualified_name: str | None,
    tags: frozenset[str] | None,
) -> bool:
    if tags is not None and die.tag not in tags:
        return False
    return qualified_name is None or die.get_full_path() == qualified_name


def query_status(found: bool, manifest_status: str) -> QueryStatus:
    if manifest_status != "complete":
        return QueryStatus.PARTIAL
    return QueryStatus.COMPLETE if found else QueryStatus.NOT_FOUND


def result(item: Any, manifest_path: Path, manifest_status: str) -> QueryResult:
    status = query_status(item is not None, manifest_status)
    return QueryResult(status, (item,) if item is not None else (), (str(manifest_path),))


def optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None

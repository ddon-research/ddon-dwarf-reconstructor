"""Regression tests for complete and early-exit Doris primary selection."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.services.definition_selection import NestedTypeCounts
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_models import DorisDie
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_queries import (
    BoundedRows,
    DorisQueryExecutor,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_store_queries import (
    DorisStoreQueryOperations,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Cursor:
    description = (
        ("unit_offset",),
        ("die_offset",),
        ("tag",),
        ("name",),
        ("target_offset",),
        ("resolution_status",),
    )

    def __init__(self, rows: Sequence[Sequence[object]]) -> None:
        self.rows = rows
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: Sequence[object] = ()) -> None:
        self.executed = query, tuple(params)

    def fetchall(self) -> Sequence[Sequence[object]]:
        return self.rows


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.cursor_value = cursor

    def cursor(self) -> _Cursor:
        return self.cursor_value


def test_complete_definition_window_reports_its_safety_ceiling() -> None:
    cursor = _Cursor(
        (
            (12, 34, "DW_TAG_class_type", "Thing", None, None),
            (13, 35, "DW_TAG_class_type", "Thing", None, None),
        )
    )
    executor = DorisQueryExecutor(_Connection(cursor), DorisConfig(database="analytical"), "a" * 64)

    result = executor.find_definition_rows_complete("Thing", max_rows=1)

    assert result.rows[0]["die_offset"] == 34
    assert result.truncated is True
    assert cursor.executed is not None
    assert "LIMIT 2" in cursor.executed[0]


def test_primary_selection_retries_a_truncated_query_with_complete_rows() -> None:
    store = Mock()
    store.manifest_path = Path("manifest.json")
    store.manifest.status = "complete"
    die = object.__new__(DorisDie)
    store._queries.find_definition_rows_complete.return_value = BoundedRows(({},), False)
    operations = DorisStoreQueryOperations(store)
    operations._definition_items = Mock(return_value=(die,))

    result = operations._complete_definition_query("Thing", qualified_name=None, tags=None)

    assert result == QueryResult(QueryStatus.COMPLETE, (die,), ("manifest.json",))
    store._queries.find_definition_rows_complete.assert_called_once_with("Thing", tags=())


def test_primary_selection_uses_the_shared_early_exit_policy() -> None:
    store = Mock()
    store.child_tag_counts.return_value = NestedTypeCounts()
    die = object.__new__(DorisDie)
    die.tag = "DW_TAG_class_type"
    die.offset = 0x20
    die.cu = SimpleNamespace(cu_offset=0x10)
    die.has_children = True
    die.attributes = {"DW_AT_byte_size": SimpleNamespace(value=16)}
    query = QueryResult(
        QueryStatus.PARTIAL,
        (die,),
        ("manifest.json",),
        ("bounded",),
        True,
    )

    result = DorisStoreQueryOperations(store)._early_primary_definition(query, "Thing")

    assert result == QueryResult(
        QueryStatus.COMPLETE,
        (die,),
        ("manifest.json",),
        ("bounded early-exit candidate satisfied selection policy",),
    )

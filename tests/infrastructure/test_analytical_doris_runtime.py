"""Focused tests for the Doris runtime query boundary."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_queries import DorisQueryExecutor


class _FakeCursor:
    def __init__(self, rows: Sequence[Sequence[object]]) -> None:
        self.description = (("unit_offset",), ("die_offset",), ("tag",), ("name",), ("target_offset",), ("resolution_status",))
        self._rows = rows
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def execute(self, operation: str, params: Sequence[object] = ()) -> None:
        self.executed = (operation, tuple(params))

    def fetchall(self) -> Sequence[Sequence[object]]:
        return self._rows


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


@pytest.mark.unit
@pytest.mark.functional
def test_definition_lookup_is_source_bound_and_parameterized() -> None:
    cursor = _FakeCursor(((12, 34, "DW_TAG_class_type", "Thing", 34, "resolved"),))
    config = DorisConfig(
        http_url="http://127.0.0.1:8030",
        stream_load_url="http://127.0.0.1:8040",
        sql_host="127.0.0.1",
        sql_port=9030,
        database="analytical",
        user="root",
        password="",
        table="dwarf",
    )
    executor = DorisQueryExecutor(_FakeConnection(cursor), config, "a" * 64)

    rows = executor.find_definition_rows("Thing; DROP TABLE dwarf_index", tags=("DW_TAG_class_type",))

    assert rows == (
        {
            "unit_offset": 12,
            "die_offset": 34,
            "tag": "DW_TAG_class_type",
            "name": "Thing",
            "target_offset": 34,
            "resolution_status": "resolved",
        },
    )
    assert cursor.executed is not None
    query, params = cursor.executed
    assert "name = %s" in query
    assert "DROP TABLE" not in query
    assert params == ("a" * 64, "definition", "Thing; DROP TABLE dwarf_index", "DW_TAG_class_type")
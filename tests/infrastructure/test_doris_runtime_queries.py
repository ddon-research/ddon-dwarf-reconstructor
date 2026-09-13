"""Focused tests for source-bound Doris query construction."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import pyarrow as pa
import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_queries import DorisQueryExecutor

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _FakeCursor:
    def __init__(self, rows: Sequence[Sequence[object]]) -> None:
        self.description = (
            ("unit_offset",),
            ("die_offset",),
            ("tag",),
            ("name",),
            ("target_offset",),
            ("resolution_status",),
        )
        self._rows = rows
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def __enter__(self) -> _FakeCursor:
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


class _FetchManyCursor(_FakeCursor):
    def __init__(self, rows: Sequence[Sequence[object]]) -> None:
        super().__init__(rows)
        self.description = (("unit_offset",), ("die_offset",))
        self.fetch_sizes: list[int] = []

    def fetchall(self) -> Sequence[Sequence[object]]:
        raise AssertionError("Arrow fallback should use fetchmany")

    def fetchmany(self, size: int) -> Sequence[Sequence[object]]:
        self.fetch_sizes.append(size)
        start = sum(self.fetch_sizes[:-1])
        return self._rows[start : start + size]


class _NativeBatchCursor(_FakeCursor):
    def __init__(self, batches: Sequence[pa.RecordBatch]) -> None:
        super().__init__(())
        self.description = (("unit_offset",), ("die_offset",))
        self._batches = batches

    def fetchall(self) -> Sequence[Sequence[object]]:
        raise AssertionError("native Arrow should not use fetchall")

    def fetch_record_batch(self) -> object:
        return iter(self._batches)


def _config() -> DorisConfig:
    return DorisConfig(
        http_url="http://127.0.0.1:8030",
        stream_load_url="http://127.0.0.1:8040",
        sql_host="127.0.0.1",
        sql_port=9030,
        database="analytical",
        user="root",
        password="",
        table="dwarf",
    )


def test_definition_lookup_is_source_bound_and_parameterized() -> None:
    cursor = _FakeCursor(((12, 34, "DW_TAG_class_type", "Thing", 34, "resolved"),))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    rows = executor.find_definition_rows(
        "Thing; DROP TABLE dwarf_index", tags=("DW_TAG_class_type",)
    )

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
    assert "`name` = %s" in query
    assert "DROP TABLE" not in query
    assert params == ("a" * 64, "definition", "Thing; DROP TABLE dwarf_index", "DW_TAG_class_type")


def test_record_batches_use_fetchmany_and_preserve_selected_schema() -> None:
    cursor = _FetchManyCursor(((7, 40), (7, 48), (7, 56)))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    batches = executor.family_record_batches(
        "die",
        {"unit_offset": 7},
        columns=("unit_offset", "die_offset"),
        batch_size=2,
    )

    assert cursor.fetch_sizes == [2, 2, 2]
    assert tuple(batch.schema.names for batch in batches) == (
        ["unit_offset", "die_offset"],
        ["unit_offset", "die_offset"],
    )
    assert [batch.to_pylist() for batch in batches] == [
        [{"unit_offset": 7, "die_offset": 40}, {"unit_offset": 7, "die_offset": 48}],
        [{"unit_offset": 7, "die_offset": 56}],
    ]


def test_record_batches_slice_native_arrow_without_python_row_fetch() -> None:
    batch = pa.RecordBatch.from_arrays(
        [pa.array([7, 7, 7]), pa.array([40, 48, 56])],
        names=["unit_offset", "die_offset"],
    )
    cursor = _NativeBatchCursor((batch,))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    batches = executor.family_record_batches(
        "die",
        {"unit_offset": 7},
        columns=("unit_offset", "die_offset"),
        batch_size=2,
    )

    assert tuple(item.num_rows for item in batches) == (2, 1)
    assert [item.column("die_offset").to_pylist() for item in batches] == [[40, 48], [56]]


def test_record_batches_normalize_doris_boolean_values() -> None:
    cursor = _FetchManyCursor(((1, 0), (True, False), ("1", "false"), (None, None)))
    cursor.description = (("has_children",), ("is_null",))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    batches = executor.family_record_batches(
        "die",
        {"unit_offset": 7},
        columns=("has_children", "is_null"),
        batch_size=3,
    )

    assert [batch.to_pylist() for batch in batches] == [
        [
            {"has_children": True, "is_null": False},
            {"has_children": True, "is_null": False},
            {"has_children": True, "is_null": False},
        ],
        [{"has_children": None, "is_null": None}],
    ]


def test_record_batches_reject_invalid_boolean_values() -> None:
    cursor = _FetchManyCursor(((2,),))
    cursor.description = (("has_children",),)
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    with pytest.raises(TypeError, match="boolean column 'has_children'"):
        executor.family_record_batches(
            "die",
            {"unit_offset": 7},
            columns=("has_children",),
        )


def test_record_batches_normalize_doris_numeric_strings() -> None:
    cursor = _FetchManyCursor((("7", "40", "0"), (None, None, None)))
    cursor.description = (("unit_offset",), ("die_offset",), ("parent_offset",))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    batches = executor.family_record_batches(
        "die",
        {"unit_offset": 7},
        columns=("unit_offset", "die_offset", "parent_offset"),
    )

    assert [batch.to_pylist() for batch in batches] == [
        [
            {"unit_offset": 7, "die_offset": 40, "parent_offset": 0},
            {"unit_offset": None, "die_offset": None, "parent_offset": None},
        ],
    ]


def test_record_batches_normalize_doris_decimal_strings() -> None:
    cursor = _FetchManyCursor((("18446744073709551615", "32"), (None, None)))
    cursor.description = (("decoded_value_uint",), ("decoded_value_size",))
    executor = DorisQueryExecutor(_FakeConnection(cursor), _config(), "a" * 64)

    batches = executor.family_record_batches(
        "attribute",
        {"unit_offset": 7},
        columns=("decoded_value_uint", "decoded_value_size"),
    )

    assert [batch.to_pylist() for batch in batches] == [
        [
            {
                "decoded_value_uint": Decimal("18446744073709551615"),
                "decoded_value_size": Decimal("32"),
            },
            {"decoded_value_uint": None, "decoded_value_size": None},
        ],
    ]

"""Focused tests for the Doris runtime query boundary."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryStatus
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_hydration import (
    hydrate_dies_by_keys,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_models import DorisDwarfInfo
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_queries import DorisQueryExecutor
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_registry import validate_registry
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_rows import restore_row
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_store import DorisDwarfStore

SOURCE_ID = "a" * 64


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


class _StoreStub(DorisDwarfStore):
    def __init__(self, rows: dict[str, list[dict[str, object]]]) -> None:
        self.manifest_path = Path("manifest.json")
        self.manifest = SimpleNamespace(
            source_identity=SimpleNamespace(sha256=SOURCE_ID),
            status="complete",
            counts={"unit": 1, "die": 3},
        )
        self._connection = SimpleNamespace(close=lambda: None)
        self._queries = SimpleNamespace(
            family_rows=lambda family, filters=None, columns=(), order_by=(), limit=None: tuple(
                _filter_rows(rows.get(family, []), filters, limit)
            )
        )
        self._config = DorisConfig(database="analytical", table="dwarf")
        self._source_id = SOURCE_ID
        self.query_log: list[tuple[str, object]] = []

        def family_rows(
            family: str,
            filters: object = None,
            columns: object = (),
            order_by: object = (),
            limit: int | None = None,
        ) -> tuple[dict[str, object], ...]:
            del columns, order_by
            self.query_log.append((family, filters))
            return tuple(_filter_rows(rows.get(family, []), filters, limit))

        self._selection_cache = None
        self._units = {}
        self._dies = {}
        self._die_unit_offsets = {}
        self._children = {}
        self._line_programs = {}
        self._child_tag_counts = {}
        self._reference_targets = {}
        self._reference_loaded = set()
        self._definition_query_cache = {}
        self._definition_name_count = None
        self._queries.family_rows = family_rows
        self.dwarf_info = DorisDwarfInfo(self)
        self.persistent_cache = SimpleNamespace()


def _filter_rows(
    rows: list[dict[str, object]], filters: object, limit: int | None
) -> list[dict[str, object]]:
    values = filters if isinstance(filters, dict) else {}
    result = [
        row
        for row in rows
        if all(
            row.get(key) in value if isinstance(value, tuple) else row.get(key) == value
            for key, value in values.items()
        )
    ]
    return result[:limit] if limit is not None else result


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


@pytest.mark.unit
@pytest.mark.functional
def test_doris_store_hydrates_attributes_children_references_and_dwarf_info() -> None:
    store = _StoreStub(_runtime_rows())

    unit = store.compilation_unit_by_offset(0)
    die = store.die_by_offset(16)
    assert die is not None
    assert unit.header == {"version": 4}
    assert die["DW_AT_name"].value == "Thing"
    assert die.get_parent() is unit.get_top_DIE()
    assert tuple(unit.get_top_DIE().iter_children()) == (die,)
    assert die.get_DIE_from_attribute("DW_AT_type") is unit.get_top_DIE()
    assert store.find_primary_definition("Thing").status is QueryStatus.COMPLETE
    assert tuple(store.dwarf_info.iter_CUs()) == (unit,)
    assert store.line_program_for_unit(0) is None
    assert store.line_program_for_unit(0) is None
    assert sum(family == "line" for family, _filters in store.query_log) == 1


@pytest.mark.unit
@pytest.mark.functional
def test_doris_store_prefetches_bounded_reference_frontier() -> None:
    rows = _prefetch_rows()
    store = _StoreStub(rows)

    store.die_by_offset(0)
    children = tuple(store.children_for_die(0))

    assert tuple(die.offset for die in children) == (16, 24)
    assert children[0].get_DIE_from_attribute("DW_AT_type").offset == 40
    assert children[1].get_DIE_from_attribute("DW_AT_type").offset == 48
    assert store.die_by_offset(40)["DW_AT_name"].value == "Target40"
    assert store.die_by_offset(48)["DW_AT_name"].value == "Target48"

    reference_queries = [filters for family, filters in store.query_log if family == "reference"]
    assert len(reference_queries) == 1
    assert reference_queries[0]["die_offset"] == (16, 24)


@pytest.mark.unit
@pytest.mark.functional
def test_doris_store_hydrates_known_dies_in_one_bounded_batch() -> None:
    store = _StoreStub(_prefetch_rows())

    dies = hydrate_dies_by_keys(store, ((0, 40), (0, 48)))

    assert tuple(die.offset for die in dies) == (40, 48)
    die_queries = [
        filters
        for family, filters in store.query_log
        if family == "die" and isinstance(filters, dict)
    ]
    assert die_queries == [{"die_offset": (40, 48)}]


@pytest.mark.unit
@pytest.mark.functional
def test_doris_store_prefetches_child_frontier_in_one_bounded_batch() -> None:
    rows = _prefetch_rows()
    _make_child_frontier(rows)
    store = _StoreStub(rows)

    assert tuple(die.offset for die in store.children_for_die(0)) == (16, 24)
    assert tuple(die.offset for die in store.children_for_die(16)) == (40,)
    assert tuple(store.children_for_die(40)) == ()

    child_queries = [
        filters
        for family, filters in store.query_log
        if family == "die" and isinstance(filters, dict) and "parent_offset" in filters
    ]
    assert child_queries == [
        {"parent_offset": 0},
        {"parent_offset": (16, 24)},
    ]


def _make_child_frontier(rows: dict[str, list[dict[str, object]]]) -> None:
    for row in rows["die"]:
        if row["die_offset"] in (16, 24):
            row["has_children"] = True
        if row["die_offset"] == 40:
            row["parent_offset"] = 16
            row["depth"] = 2
        if row["die_offset"] == 48:
            row["parent_offset"] = 24
            row["depth"] = 2


def _prefetch_rows() -> dict[str, list[dict[str, object]]]:
    common = {"record_type": "die", "source_id": SOURCE_ID, "unit_offset": 0}
    die_rows = [
        common
        | {
            "die_offset": 0,
            "ordinal": 0,
            "tag": "DW_TAG_compile_unit",
            "depth": 0,
            "has_children": True,
            "parent_offset": None,
            "is_null": False,
        }
    ]
    for offset, parent, tag in (
        (16, 0, "DW_TAG_variable"),
        (24, 0, "DW_TAG_variable"),
        (40, None, "DW_TAG_base_type"),
        (48, None, "DW_TAG_base_type"),
    ):
        die_rows.append(
            common
            | {
                "die_offset": offset,
                "ordinal": offset // 8,
                "tag": tag,
                "depth": 1,
                "has_children": False,
                "parent_offset": parent,
                "is_null": False,
            }
        )
    return {
        "unit": [_unit_row()],
        "die": die_rows,
        "attribute": [
            _name_attribute(16, "Child16"),
            _reference_attribute(16),
            _name_attribute(24, "Child24"),
            _reference_attribute(24),
            _name_attribute(40, "Target40"),
            _name_attribute(48, "Target48"),
        ],
        "reference": [
            _reference_for(16, 40),
            _reference_for(24, 48),
        ],
        "index": [],
        "line": [],
    }


@pytest.mark.unit
@pytest.mark.functional
def test_restore_row_converts_doris_largeint_uint_strings() -> None:
    row = {
        "record_type": "attribute",
        "decoded_value_kind": "uint",
        "decoded_value_uint": "8",
        "raw_value_kind": "uint",
        "raw_value_uint": "8",
    }

    restored = restore_row(row)

    assert restored["decoded_value"] == 8
    assert restored["raw_value"] == 8


def _runtime_rows() -> dict[str, list[dict[str, object]]]:
    return {
        "unit": [_unit_row()],
        "die": _die_rows(),
        "attribute": [_attribute_row()],
        "reference": [_reference_row()],
        "index": [_index_row()],
        "line": [],
    }


def _unit_row() -> dict[str, object]:
    return {
        "record_type": "unit",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "unit_length": 32,
        "header_json": '{"version":4}',
        "unit_type": "DW_UT_compile",
    }


def _die_rows() -> list[dict[str, object]]:
    common = {"record_type": "die", "source_id": SOURCE_ID, "unit_offset": 0}
    return [
        common
        | {
            "die_offset": 0,
            "ordinal": 0,
            "tag": "DW_TAG_compile_unit",
            "depth": 0,
            "has_children": True,
            "parent_offset": None,
            "is_null": False,
        },
        common
        | {
            "die_offset": 16,
            "ordinal": 1,
            "tag": "DW_TAG_class_type",
            "depth": 1,
            "has_children": False,
            "parent_offset": 0,
            "is_null": False,
        },
        common
        | {
            "die_offset": 32,
            "ordinal": 2,
            "tag": None,
            "depth": 1,
            "has_children": False,
            "parent_offset": 0,
            "is_null": True,
        },
    ]


def _attribute_row() -> dict[str, object]:
    return {
        "record_type": "attribute",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": 16,
        "ordinal": 0,
        "name": "DW_AT_name",
        "form": "DW_FORM_string",
        "raw_value_kind": "text",
        "raw_value_text": "Thing",
        "decoded_value_kind": "text",
        "decoded_value_text": "Thing",
    }


def _name_attribute(die_offset: int, name: str) -> dict[str, object]:
    return {
        "record_type": "attribute",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": die_offset,
        "ordinal": 0,
        "name": "DW_AT_name",
        "form": "DW_FORM_string",
        "raw_value_kind": "text",
        "raw_value_text": name,
        "decoded_value_kind": "text",
        "decoded_value_text": name,
    }


def _reference_attribute(die_offset: int) -> dict[str, object]:
    return {
        "record_type": "attribute",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": die_offset,
        "ordinal": 1,
        "name": "DW_AT_type",
        "form": "DW_FORM_ref4",
        "raw_value_kind": "uint",
        "raw_value_uint": 0,
        "decoded_value_kind": "uint",
        "decoded_value_uint": 0,
    }


def _reference_row() -> dict[str, object]:
    return {
        "record_type": "reference",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": 16,
        "attribute_name": "DW_AT_type",
        "relation": "attribute_reference",
        "target_offset": 0,
    }


def _reference_for(die_offset: int, target_offset: int) -> dict[str, object]:
    return {
        "record_type": "reference",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": die_offset,
        "attribute_name": "DW_AT_type",
        "relation": "attribute_reference",
        "target_offset": target_offset,
    }


def _index_row() -> dict[str, object]:
    return {
        "record_type": "index",
        "source_id": SOURCE_ID,
        "unit_offset": 0,
        "die_offset": 16,
        "index_type": "definition",
        "name": "Thing",
        "tag": "DW_TAG_class_type",
    }


@pytest.mark.unit
@pytest.mark.functional
def test_registry_validation_rejects_missing_publication() -> None:
    manifest = SimpleNamespace(
        source_identity=SimpleNamespace(sha256=SOURCE_ID),
        schema_version="1.1",
        counts={"unit": 1},
    )
    cursor = _FakeCursor(())
    connection = _FakeConnection(cursor)

    with pytest.raises(RuntimeError, match="unavailable"):
        validate_registry(connection, "analytical", "dwarf", manifest)

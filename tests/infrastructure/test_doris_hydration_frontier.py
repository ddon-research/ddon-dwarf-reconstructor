"""Regression tests for complete cached Doris hydration frontiers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical import doris_hydration
from tests.infrastructure.test_analytical_doris_runtime import (
    _make_child_frontier,
    _prefetch_rows,
    _StoreStub,
)

pytestmark = [pytest.mark.unit, pytest.mark.performance, pytest.mark.non_functional]


def test_offset_frontier_returns_previously_cached_dies(monkeypatch) -> None:
    cached = object()
    store = SimpleNamespace(_dies={40: cached})
    hydrate = Mock()
    monkeypatch.setattr(doris_hydration, "_hydrate_offsets", hydrate)

    result = doris_hydration.hydrate_dies_by_offsets(store, (40,))

    assert result == (cached,)
    hydrate.assert_called_once_with(store, (40,))


@pytest.mark.regression
def test_global_child_frontier_keeps_duplicate_parent_offsets_by_cu() -> None:
    rows = _prefetch_rows()
    _make_child_frontier(rows)
    rows["unit"].append(_unit_row_for_test(100))
    parent = next(row for row in rows["die"] if row["die_offset"] == 16)
    rows["die"].append(parent | {"unit_offset": 100})
    child = next(row for row in rows["die"] if row["die_offset"] == 40)
    rows["die"].append(
        child
        | {
            "unit_offset": 100,
            "die_offset": 140,
            "ordinal": 5,
            "parent_offset": 16,
            "tag": "DW_TAG_union_type",
        }
    )
    next(row for row in rows["die"] if row["die_offset"] == 40)["tag"] = "DW_TAG_structure_type"
    store = _StoreStub(rows)

    parents = doris_hydration.hydrate_dies_by_keys(store, ((0, 16), (100, 16)))
    doris_hydration.prefetch_children(store, parents)
    doris_hydration.prime_child_tag_counts(store, parents)

    assert tuple(die.offset for die in store.children_for_die(16, 0)) == (40,)
    assert tuple(die.offset for die in store.children_for_die(16, 100)) == (140,)
    assert store.child_tag_counts(16, 0).structs == 1
    assert store.child_tag_counts(16, 100).unions == 1
    assert store.operation_log.count("prefetch_children") == 1
    assert store.operation_log.count("prefetch_child_tag_counts") == 1


def _unit_row_for_test(unit_offset: int) -> dict[str, object]:
    return {
        "record_type": "unit",
        "source_id": "a" * 64,
        "unit_offset": unit_offset,
        "unit_length": 32,
        "header_json": '{"version":4}',
        "unit_type": "DW_UT_compile",
    }

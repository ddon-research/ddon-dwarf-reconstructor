"""Request-scoped cache lifecycle contracts for the Doris adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.bounded_query_cache import (
    BoundedQueryCache,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_store import DorisDwarfStore

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_begin_root_clears_hydration_caches_but_resets_metrics() -> None:
    store = object.__new__(DorisDwarfStore)
    store._units = {1: object()}
    store._dies = {2: object()}
    store._die_unit_offsets = {2: 1}
    store._children = {2: ()}
    store._line_programs = {1: None}
    store._child_tag_counts = {2: object()}
    store._reference_targets = {(1, 2, "type"): 3}
    store._reference_loaded = {(1, 2)}
    store._definition_query_cache = BoundedQueryCache()
    store._definition_query_cache[("Thing", None, None)] = object()
    store._active_root = "previous"
    store._cache_hits = 7
    store._cache_misses = 4

    store.begin_root("Thing")

    assert store._active_root == "Thing"
    assert store._cache_hits == 0
    assert store._cache_misses == 0
    assert store._request_cache_sizes() == {
        "units": 0,
        "dies": 0,
        "die_unit_offsets": 0,
        "children": 0,
        "line_programs": 0,
        "child_tag_counts": 0,
        "reference_targets": 0,
        "reference_loaded": 0,
        "definition_queries": 0,
        "definition_query_evictions": 0,
    }


def test_end_root_is_idempotent_without_an_active_root() -> None:
    store = object.__new__(DorisDwarfStore)
    store._active_root = None
    store._cache_hits = 0
    store._cache_misses = 0
    store._units = {}
    store._dies = {}
    store._die_unit_offsets = {}
    store._children = {}
    store._line_programs = {}
    store._child_tag_counts = {}
    store._reference_targets = {}
    store._reference_loaded = set()
    store._definition_query_cache = BoundedQueryCache()

    store.end_root()

    assert store._active_root is None


def test_close_is_idempotent_and_closes_connection_after_query_cleanup() -> None:
    store = object.__new__(DorisDwarfStore)
    store._closed = False
    store._queries = MagicMock()
    store._connection = MagicMock()

    store.close()
    store.close()

    store._queries.close.assert_called_once_with()
    store._connection.close.assert_called_once_with()
    assert store._closed is True

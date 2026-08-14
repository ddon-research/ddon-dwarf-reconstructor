"""Doris lookup hints must not consume non-complete query evidence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_cache import DorisCache
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_index import DorisDwarfIndex
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_store_queries import (
    DorisStoreQueryOperations,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


@pytest.mark.parametrize("status", [QueryStatus.PARTIAL, QueryStatus.UNAVAILABLE])
def test_doris_index_does_not_expose_offset_from_non_complete_result(
    status: QueryStatus,
) -> None:
    store = Mock()
    store.find_primary_definition.return_value = QueryResult(
        status,
        (Mock(offset=0x20),),
        diagnostics=("bounded query incomplete",),
    )

    assert DorisDwarfIndex(store).find_symbol_offset("Thing") is None


@pytest.mark.parametrize("status", [QueryStatus.PARTIAL, QueryStatus.UNAVAILABLE])
def test_doris_cache_does_not_publish_non_complete_definition_hints(
    status: QueryStatus,
) -> None:
    store = Mock()
    candidate = Mock(offset=0x20, cu=Mock(cu_offset=0x10), attributes={})
    store.find_primary_definition.return_value = QueryResult(
        status,
        (candidate,),
        diagnostics=("bounded query incomplete",),
    )
    cache = DorisCache(store)

    assert cache.get_symbol_offset("Thing") is None
    assert cache.get_symbol_cu_offset("Thing") is None
    assert cache.get_symbol_completeness("Thing") is None


def test_source_bound_selection_cache_hydrates_complete_primary_without_bounded_query() -> None:
    store = Mock()
    store.manifest_path = Path("manifest.json")
    store.manifest.status = "complete"
    store._selection_cache.get_symbol_completeness.return_value = True
    store._selection_cache.get_symbol_offset.return_value = 0x20
    die = Mock(offset=0x20, attributes={"DW_AT_name": Mock(value=b"Thing")})
    store.die_by_offset.return_value = die

    query = DorisStoreQueryOperations(store).find_primary_definition("Thing")

    assert query == QueryResult(QueryStatus.COMPLETE, (die,), ("manifest.json",))
    store.die_by_offset.assert_called_once_with(0x20)
    store._queries.find_definition_rows_bounded.assert_not_called()

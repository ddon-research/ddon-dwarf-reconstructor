"""Parquet selection hints must not promote incomplete evidence."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    MaterializationManifest,
    QueryResult,
    QueryStatus,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.bounded_query_cache import (
    BoundedQueryCache,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_store_queries import (
    ParquetStoreQueries,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_incomplete_selection_hint_falls_back_to_complete_parquet_query() -> None:
    store = object.__new__(ParquetStoreQueries)
    store.manifest_path = Path("manifest.json")
    store.manifest = cast(MaterializationManifest, SimpleNamespace(status="complete"))
    store._selection_cache = Mock()
    store._selection_cache.get_symbol_completeness.return_value = False
    store._selection_cache.get_symbol_offset.return_value = 0x20
    store._definition_query_cache = BoundedQueryCache()
    store._payload_rows = Mock(return_value=[{"die_offset": 0x20}])
    store._die_for_index_record = Mock(return_value=SimpleNamespace(offset=0x20, attributes={}))
    fallback = QueryResult(
        QueryStatus.PARTIAL,
        (SimpleNamespace(offset=0x30),),
        ("manifest.json",),
        ("bounded definition evidence",),
        True,
    )
    store.find_definitions = Mock(return_value=fallback)

    result = store.find_primary_definition("Thing")

    assert result == fallback
    store.find_definitions.assert_called_once_with("Thing", qualified_name=None, tags=None)


def test_complete_selection_hint_can_hydrate_without_broad_parquet_query() -> None:
    store = object.__new__(ParquetStoreQueries)
    store.manifest_path = Path("manifest.json")
    store.manifest = cast(MaterializationManifest, SimpleNamespace(status="complete"))
    store._selection_cache = Mock()
    store._selection_cache.get_symbol_completeness.return_value = True
    store._selection_cache.get_symbol_offset.return_value = 0x20
    store._payload_rows = Mock(return_value=[{"die_offset": 0x20}])
    die = SimpleNamespace(offset=0x20, attributes={})
    store._die_for_index_record = Mock(return_value=die)
    store.find_definitions = Mock()

    result = store.find_primary_definition("Thing")

    assert result == QueryResult(QueryStatus.COMPLETE, (die,), ("manifest.json",))
    store.find_definitions.assert_not_called()

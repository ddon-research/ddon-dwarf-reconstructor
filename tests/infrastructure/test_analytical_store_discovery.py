"""Analytical-store discovery boundary tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.services.definition_selection import DefinitionCandidate
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_discovery import (
    ClassParserDiscoveryMixin,
)
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_lazy_discovery import (
    ClassParserLazyDiscoveryMixin,
)
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_scan import ClassParserScanMixin
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_store_discovery_refuses_cu_scan_after_analytical_miss() -> None:
    query_port = Mock()
    query_port.find_primary_definition.return_value = QueryResult(QueryStatus.NOT_FOUND, ())
    context = SimpleNamespace(query_port=query_port)
    with patch.object(ClassParserScanMixin, "_find_class_full_scan") as full_scan:
        result = ClassParserDiscoveryMixin._find_class_from_store(context, "Missing")

    assert result is None
    full_scan.assert_not_called()


@pytest.mark.parametrize("status", [QueryStatus.PARTIAL, QueryStatus.UNAVAILABLE])
def test_store_discovery_propagates_non_complete_empty_results(status: QueryStatus) -> None:
    query_port = Mock()
    query_port.find_primary_definition.return_value = QueryResult(
        status,
        (),
        diagnostics=("backend unavailable",),
    )
    context = SimpleNamespace(query_port=query_port)

    with pytest.raises(RuntimeError, match="source-bound generation cannot continue"):
        ClassParserDiscoveryMixin._find_class_from_store(context, "Broken")


def test_store_discovery_rejects_all_partial_candidates() -> None:
    candidate = Mock(
        tag="DW_TAG_class_type",
        has_children=False,
        attributes={},
        cu=Mock(),
    )
    query_port = Mock()
    query_port.find_primary_definition.return_value = QueryResult(
        QueryStatus.PARTIAL,
        (candidate,),
        diagnostics=("query truncated",),
    )
    context = SimpleNamespace(query_port=query_port)

    with pytest.raises(RuntimeError, match="query truncated"):
        ClassParserDiscoveryMixin._find_class_from_store(context, "Truncated")


def test_lazy_discovery_does_not_consume_partial_search_evidence() -> None:
    lazy_index = Mock()
    lazy_index.targeted_symbol_search.return_value = SearchResult(
        SearchStatus.PARTIAL,
        DefinitionCandidate("Partial", 0x10, 0x20, 0, False),
        0.1,
        1,
        ("search timed out",),
    )
    context = SimpleNamespace(lazy_index=lazy_index)
    context._find_die_and_cu_by_offset = Mock(return_value=(Mock(), Mock()))

    assert ClassParserLazyDiscoveryMixin._targeted_definition(context, "Partial") is None
    context._find_die_and_cu_by_offset.assert_not_called()

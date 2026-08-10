"""Store-backed discovery tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_discovery import (
    ClassParserDiscoveryMixin,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_store_discovery_includes_namespace_roots() -> None:
    query_port = Mock()
    namespace_die = SimpleNamespace(
        tag="DW_TAG_namespace",
        cu=SimpleNamespace(cu_offset=0x10),
    )
    query_port.find_primary_definition.return_value = QueryResult(
        QueryStatus.COMPLETE, (namespace_die,)
    )
    context = SimpleNamespace(query_port=query_port)

    result = ClassParserDiscoveryMixin._find_class_from_store(context, "rAcquirement")

    assert result == (namespace_die.cu, namespace_die)
    requested_tags = query_port.find_primary_definition.call_args.kwargs["tags"]
    assert "DW_TAG_namespace" in requested_tags

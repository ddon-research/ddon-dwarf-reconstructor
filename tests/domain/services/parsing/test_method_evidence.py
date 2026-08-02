"""Tests for method implementation evidence helpers."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import ParameterInfo
from ddon_dwarf_reconstructor.domain.services.parsing.method_evidence import (
    merge_parameter_names,
    score_implementation,
)


@pytest.mark.unit
def test_implementation_scoring_uses_one_child_traversal() -> None:
    named = Mock(tag="DW_TAG_formal_parameter")
    named.attributes = {"DW_AT_name": Mock(value=b"value")}
    unnamed = Mock(tag="DW_TAG_formal_parameter")
    unnamed.attributes = {}
    block = Mock(tag="DW_TAG_lexical_block")
    block.attributes = {}
    implementation = Mock()
    implementation.attributes = {"DW_AT_low_pc": Mock(), "DW_AT_inline": Mock()}
    implementation.iter_children.return_value = [named, unnamed, block]

    assert score_implementation(implementation) == 1160
    implementation.iter_children.assert_called_once_with()


@pytest.mark.unit
def test_parameter_merge_skips_artificial_parameters() -> None:
    artificial = Mock(tag="DW_TAG_formal_parameter")
    artificial.attributes = {"DW_AT_artificial": Mock(), "DW_AT_name": Mock(value=b"this")}
    first = Mock(tag="DW_TAG_formal_parameter")
    first.attributes = {"DW_AT_name": Mock(value=b"count")}
    second = Mock(tag="DW_TAG_formal_parameter")
    second.attributes = {"DW_AT_name": Mock(value="scale")}
    implementation = Mock()
    implementation.iter_children.return_value = [artificial, first, second]
    parameters = [
        ParameterInfo(name="__artificial__", type_name="Owner*"),
        ParameterInfo(name="param1", type_name="int"),
        ParameterInfo(name="param2", type_name="float"),
    ]

    assert merge_parameter_names(implementation, parameters, "apply") == 2
    assert [parameter.name for parameter in parameters] == [
        "__artificial__",
        "count",
        "scale",
    ]


@pytest.mark.unit
def test_parameter_merge_uses_proven_common_prefix_on_count_mismatch() -> None:
    child = Mock(tag="DW_TAG_formal_parameter")
    child.attributes = {"DW_AT_name": Mock(value=b"only")}
    implementation = Mock()
    implementation.iter_children.return_value = [child]
    parameters = [
        ParameterInfo(name="param1", type_name="int"),
        ParameterInfo(name="param2", type_name="int"),
    ]

    assert merge_parameter_names(implementation, parameters, "partial") == 1
    assert [parameter.name for parameter in parameters] == ["only", "param2"]

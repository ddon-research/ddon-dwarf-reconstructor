"""Focused array/declarator parsing tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing.array_parser import (
    ArrayInfo,
    parse_array_type,
)


def _attribute(value: object) -> Mock:
    return Mock(value=value)


def _subrange(
    *, count: object | None = None, upper: object | None = None, lower: object | None = None
) -> Mock:
    child = Mock(tag="DW_TAG_subrange_type")
    child.attributes = {}
    if count is not None:
        child.attributes["DW_AT_count"] = _attribute(count)
    if upper is not None:
        child.attributes["DW_AT_upper_bound"] = _attribute(upper)
    if lower is not None:
        child.attributes["DW_AT_lower_bound"] = _attribute(lower)
    return child


def _array_die(element: Mock | None, children: list[Mock]) -> Mock:
    array_die = Mock(offset=0x1000)
    array_die.attributes = {"DW_AT_type": _attribute(element.offset if element else 0)}
    array_die.get_DIE_from_attribute.return_value = element
    array_die.iter_children.return_value = children
    return array_die


@pytest.mark.unit
def test_array_without_type_reference_is_unresolved() -> None:
    array_die = Mock(attributes={}, offset=0x1000)

    assert parse_array_type(array_die, Mock()) is None


@pytest.mark.unit
def test_array_element_resolution_errors_are_recoverable() -> None:
    element = Mock(offset=0x2000)
    resolver = Mock()
    resolver.resolve_type_name.side_effect = ValueError("bad DIE")

    assert parse_array_type(_array_die(element, []), resolver) is None


@pytest.mark.unit
def test_array_counts_and_bounds_form_multidimensional_name() -> None:
    element = Mock(offset=0x2000)
    resolver = Mock()
    resolver.resolve_type_name.return_value = "Value"
    children = [_subrange(count=4), _subrange(upper=5, lower=2)]

    result = parse_array_type(_array_die(element, children), resolver)

    assert result is not None
    assert result.name == "Value[4][4]"
    assert result.dimensions == (4, 4)
    assert result.total_elements == 16
    assert result.declarator.render() == "Value[4][4]"


@pytest.mark.unit
def test_array_invalid_and_missing_bounds_become_unspecified_dimensions() -> None:
    element = Mock(offset=0x2000)
    resolver = Mock()
    resolver.resolve_type_name.return_value = "Value"
    children = [_subrange(count="invalid"), _subrange(), _subrange(upper=1, lower=3)]

    result = parse_array_type(_array_die(element, children), resolver)

    assert result is not None
    assert result.dimensions == (0, 0, 0)
    assert result.name == "Value[][][]"
    assert result.total_elements == 1


@pytest.mark.unit
def test_array_info_legacy_mapping_access_remains_supported() -> None:
    info = ArrayInfo("Value[2]", "Value", (2,), 2, 0x1234)

    assert info["name"] == info.name
    assert info["element_type"] == "Value"
    assert info["dimensions"] == (2,)
    assert info["total_elements"] == 2
    assert info["die_offset"] == 0x1234
    assert info.as_dict()["dimensions"] == [2]
    with pytest.raises(KeyError):
        info["unknown"]

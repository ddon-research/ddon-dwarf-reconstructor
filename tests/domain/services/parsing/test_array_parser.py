"""Array metadata projects the same ordered declarator used by generation."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.domain.services.parsing.array_parser import parse_array_type
from ddon_dwarf_reconstructor.domain.services.parsing.type_reference_parser import (
    TypeReferenceParser,
)
from tests.support.type_graph import TypeAttribute, TypeDie

pytestmark = [pytest.mark.unit, pytest.mark.regression]


class _Resolver:
    def __init__(self) -> None:
        self.parser = TypeReferenceParser()

    def resolve_type_reference(self, die: TypeDie):
        return self.parser.parse(die)


def _array(offset: int, element: TypeDie, *counts: object) -> TypeDie:
    children = [
        TypeDie(
            "DW_TAG_subrange_type",
            offset + index + 1,
            {"DW_AT_count": TypeAttribute(count)},
        )
        for index, count in enumerate(counts)
    ]
    return TypeDie("DW_TAG_array_type", offset, children=children).link(element)


def test_array_without_type_reference_is_unresolved() -> None:
    assert parse_array_type(TypeDie("DW_TAG_array_type", 1), _Resolver()) is None


def test_array_resolution_errors_are_recoverable() -> None:
    array = _array(1, TypeDie("DW_TAG_base_type", 0).named("int"), 3)
    resolver = Mock()
    resolver.resolve_type_reference.side_effect = ValueError("bad DIE")
    assert parse_array_type(array, resolver) is None


def test_array_counts_and_bounds_form_multidimensional_declarator() -> None:
    base = TypeDie("DW_TAG_base_type", 0).named("int")
    array = _array(10, base, 4)
    array.children.append(
        TypeDie(
            "DW_TAG_subrange_type",
            12,
            {"DW_AT_upper_bound": TypeAttribute(5), "DW_AT_lower_bound": TypeAttribute(2)},
        )
    )

    result = parse_array_type(array, _Resolver())

    assert result is not None
    assert result.name == "int[4][4]"
    assert result.dimensions == (4, 4)
    assert result.total_elements == 16
    assert result.declarator.render("values") == "int values[4][4]"


def test_array_pointer_elements_preserve_indirection() -> None:
    target = TypeDie("DW_TAG_class_type", 0).named("Texture")
    pointer = TypeDie("DW_TAG_pointer_type", 1).link(target)
    result = parse_array_type(_array(2, pointer, 2), _Resolver())

    assert result is not None
    assert result.name == "Texture*[2]"
    assert result.element_type == "Texture*"
    assert result.declarator.render("items") == "Texture *items[2]"


def test_array_invalid_bounds_stay_unresolved_instead_of_truncating() -> None:
    base = TypeDie("DW_TAG_base_type", 0).named("int")
    array = _array(10, base, 2.5, True, Decimal("3"))

    result = parse_array_type(array, _Resolver())

    assert result is not None
    assert result.dimensions == (None, None, 3)
    assert result.total_elements is None
    assert result.declarator.render("values") == "int values[][][3]"


def test_nested_array_alias_and_offset_zero_keep_outer_first() -> None:
    target = TypeDie("DW_TAG_class_type", 0).named("Texture")
    alias = TypeDie("DW_TAG_typedef", 1).named("TextureAlias").link(target)
    pointer = TypeDie("DW_TAG_pointer_type", 2).link(alias)
    inner = _array(3, pointer, 2)
    outer = _array(5, inner, 3)

    result = parse_array_type(outer, _Resolver())

    assert result is not None
    assert result.dimensions == (3, 2)
    assert result.element_type == "TextureAlias*"
    assert result.declarator.render("items") == "TextureAlias *items[3][2]"
    assert result.reference.die_offset == 1


def test_array_of_function_pointers_uses_callable_precedence() -> None:
    result_type = TypeDie("DW_TAG_base_type", 0).named("int")
    function = TypeDie("DW_TAG_subroutine_type", 1).link(result_type)
    pointer = TypeDie("DW_TAG_pointer_type", 2).link(function)
    result = parse_array_type(_array(3, pointer, 4), _Resolver())

    assert result is not None
    assert result.declarator.render("callbacks") == "int (*callbacks[4])()"


@given(st.lists(st.integers(min_value=0, max_value=128), min_size=1, max_size=4))
def test_array_extents_match_structured_reference_in_source_order(counts: list[int]) -> None:
    element = TypeDie("DW_TAG_base_type", 0).named("int")
    for index, count in reversed(list(enumerate(counts, start=1))):
        element = _array(index * 10, element, count)
    result = parse_array_type(element, _Resolver())

    assert result is not None
    assert result.dimensions == tuple(counts)
    assert result.name == result.reference.name
    assert result.declarator.render("values") == "int values" + "".join(
        f"[{count}]" for count in counts
    )

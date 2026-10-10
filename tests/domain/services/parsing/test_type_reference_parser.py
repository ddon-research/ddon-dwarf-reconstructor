"""Declarator precedence, scoped identity, and incomplete evidence regressions."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
)
from ddon_dwarf_reconstructor.domain.services.parsing.type_reference_parser import (
    TypeReferenceParser,
)
from ddon_dwarf_reconstructor.domain.services.parsing.type_scope import lexical_scope
from tests.support.type_graph import TypeAttribute, TypeDie, TypeUnit

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.mark.parametrize(
    "kind,explicit,expected",
    [
        ("class", None, "private"),
        ("struct", None, "public"),
        ("union", None, "public"),
        ("class", 1, "public"),
        ("class", 2, "protected"),
    ],
)
def test_alias_access_uses_evidence_or_lexical_default(kind, explicit, expected) -> None:
    owner = TypeDie(f"DW_TAG_{'structure' if kind == 'struct' else kind}_type", 1).named("Owner")
    alias = (
        TypeDie("DW_TAG_typedef", 2, parent=owner)
        .named("Alias")
        .link(TypeDie("DW_TAG_base_type", 3).named("int"))
    )
    if explicit is not None:
        alias.attributes["DW_AT_accessibility"] = TypeAttribute(explicit)
    assert TypeReferenceParser().parse(alias).declaration_access == expected


def test_nested_owner_and_callable_parameter_dependencies_keep_qualified_identities() -> None:
    namespace = TypeDie("DW_TAG_namespace", 1).named("ns")
    outer = TypeDie("DW_TAG_class_type", 2, parent=namespace).named("Outer<int>")
    owner = TypeDie("DW_TAG_class_type", 3, parent=outer).named("Inner")
    result = TypeDie("DW_TAG_base_type", 4).named("bool")
    argument = TypeDie("DW_TAG_structure_type", 5, parent=namespace).named("Argument")
    pointer = TypeDie("DW_TAG_pointer_type", 6).link(argument)
    parameter = TypeDie("DW_TAG_formal_parameter", 7).link(pointer)
    function = TypeDie("DW_TAG_subroutine_type", 8, children=[parameter]).link(result)
    function.attributes["DW_AT_const"] = TypeAttribute(True)
    function.attributes["DW_AT_noexcept"] = TypeAttribute(False)
    member = (
        TypeDie("DW_TAG_ptr_to_member_type", 9).link(function).link(owner, "DW_AT_containing_type")
    )
    reference = TypeReferenceParser().parse(member)
    assert (
        reference.declarator.render("callback")
        == "bool (ns::Outer<int>::Inner::*callback)(ns::Argument*) const"
    )
    names = {item.declarator.base_name for item in reference.references()}
    assert names == {"bool", "ns::Outer<int>::Inner", "ns::Argument"}
    assert lexical_scope(owner).containing_aggregate == "ns::Outer<int>"
    assert not lexical_scope(owner).namespace_only


def test_pointer_qualifiers_do_not_become_pointee_qualifiers() -> None:
    integer = TypeDie("DW_TAG_base_type", 0).named("int")
    const_integer = TypeDie("DW_TAG_const_type", 1).link(integer)
    pointer = TypeDie("DW_TAG_pointer_type", 2).link(const_integer)
    const_pointer = TypeDie("DW_TAG_const_type", 3).link(pointer)
    assert TypeReferenceParser().parse(const_pointer).declarator.render("p") == "const int *const p"


@pytest.mark.parametrize(
    "outer,inner,expected",
    [
        ("pointer", "array", "int (*p)[3]"),
        ("array", "pointer", "int *p[3]"),
        ("reference", "array", "int (&p)[3]"),
        ("pointer", "function", "int (*p)()"),
        ("function", "pointer", "int *p()"),
    ],
)
def test_declarator_precedence(outer: str, inner: str, expected: str) -> None:
    tags = {
        "pointer": "DW_TAG_pointer_type",
        "reference": "DW_TAG_reference_type",
        "array": "DW_TAG_array_type",
        "function": "DW_TAG_subroutine_type",
    }
    base = TypeDie("DW_TAG_base_type", 0).named("int")
    first = TypeDie(tags[inner], 1).link(base)
    second = TypeDie(tags[outer], 2).link(first)
    array = first if inner == "array" else second if outer == "array" else None
    if array is not None:
        array.children.append(
            TypeDie("DW_TAG_subrange_type", 3, attributes={"DW_AT_count": TypeAttribute(3)})
        )
    assert TypeReferenceParser().parse(second).declarator.render("p") == expected


def test_same_offset_in_distinct_units_and_alias_identity_are_retained() -> None:
    first = TypeDie("DW_TAG_class_type", 0, cu=TypeUnit(10)).named("First")
    second = TypeDie("DW_TAG_class_type", 0, cu=TypeUnit(20)).named("Second")
    alias = TypeDie("DW_TAG_typedef", 2, cu=TypeUnit(20)).named("Alias").link(second)
    parser = TypeReferenceParser()
    assert parser.parse(first).name == "First"
    assert parser.parse(second).name == "Second"
    parsed = parser.parse(alias)
    assert parsed.name == "Alias"
    assert parsed.alias_target is not None
    assert parsed.alias_target.name == "Second"
    assert parsed.alias_target.cu_offset == 20


def test_incomplete_cu_identity_is_not_reused_as_a_cache_key() -> None:
    first = TypeDie("DW_TAG_base_type", 0, cu=None).named("First")
    second = TypeDie("DW_TAG_base_type", 0, cu=None).named("Second")
    parser = TypeReferenceParser()

    assert parser.parse(first).name == "First"
    assert parser.parse(second).name == "Second"


def test_missing_member_owner_and_typedef_cycles_remain_diagnostics() -> None:
    integer = TypeDie("DW_TAG_base_type", 1).named("int")
    member = TypeDie("DW_TAG_ptr_to_member_type", 2).link(integer)
    parsed = TypeReferenceParser().parse(member)
    assert parsed.diagnostics
    assert parsed.name != "int"
    first = TypeDie("DW_TAG_typedef", 3).named("First")
    second = TypeDie("DW_TAG_typedef", 4).named("Second").link(first)
    first.link(second)
    assert "cyclic" in TypeReferenceParser().parse(first).diagnostics[0]


def test_false_artificial_flag_retains_parameter_and_variadic_is_preserved() -> None:
    integer = TypeDie("DW_TAG_base_type", 1).named("int")
    argument = TypeDie("DW_TAG_formal_parameter", 2).link(integer)
    argument.attributes["DW_AT_artificial"] = TypeAttribute(False)
    variadic = TypeDie("DW_TAG_unspecified_parameters", 3)
    function = TypeDie("DW_TAG_subroutine_type", 4, children=[argument, variadic])
    assert TypeReferenceParser().parse(function).declarator.render("f") == "void f(int, ...)"


def test_specification_scope_and_unknown_local_scope_are_distinct() -> None:
    namespace = TypeDie("DW_TAG_namespace", 1).named("ns")
    declaration = TypeDie("DW_TAG_class_type", 2, parent=namespace).named("Thing")
    definition = TypeDie("DW_TAG_class_type", 3).link(declaration, "DW_AT_specification")
    assert TypeReferenceParser().parse(definition).name == "ns::Thing"
    local = TypeDie("DW_TAG_class_type", 4, parent=TypeDie("DW_TAG_subprogram", 5)).named("Local")
    assert not lexical_scope(local).complete


@given(st.lists(st.integers(min_value=0, max_value=1024), min_size=1, max_size=5))
def test_array_extents_remain_in_source_order(dimensions: list[int]) -> None:
    layers = tuple(DeclaratorLayer("array", extent=dimension) for dimension in dimensions)
    declaration = TypeDeclarator("int", layers=layers)
    assert declaration.render("data") == "int data" + "".join(f"[{size}]" for size in dimensions)

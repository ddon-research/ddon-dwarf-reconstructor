"""Overload correspondence and conflicting declaration evidence stay separate."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.domain.models.dwarf import MethodInfo, ParameterInfo
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.services.generation.method_signature_policy import (
    MethodDeclarationError,
    canonical_method_signature,
    canonical_parameter_type,
    method_declaration_conflicts,
    method_overload_key,
    unique_method_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.mark.parametrize(
    "other",
    [
        MethodInfo("f", "float"),
        MethodInfo("f", "int", is_noexcept=True),
        MethodInfo("f", "int", is_static=True),
        MethodInfo("f", "int", is_virtual=True),
        MethodInfo("f", "int", access="private"),
        MethodInfo("f", "int", is_deleted=True),
        MethodInfo("f", "int", is_defaulted=True),
        MethodInfo("f", "int", is_noreturn=True),
    ],
)
def test_declaration_attributes_cannot_create_overloads(other: MethodInfo) -> None:
    first = MethodInfo("f", "int")
    assert method_overload_key(first) == method_overload_key(other)
    assert method_declaration_conflicts([first, other])
    with pytest.raises(MethodDeclarationError, match="conflicting method declaration"):
        unique_method_declarations([first, other], method_overload_key)


@pytest.mark.parametrize("qualifier", ["&", "&&"])
@pytest.mark.parametrize("is_const", [False, True])
def test_unqualified_and_ref_qualified_overloads_collide(qualifier: str, is_const: bool) -> None:
    first = MethodInfo("f", "int", is_const=True)
    second = replace(first, is_const=is_const, ref_qualifier=qualifier)
    assert method_declaration_conflicts([first, second])


@pytest.mark.parametrize("qualifier", [None, "&", "&&"])
def test_static_and_cv_ref_qualified_nonstatic_declarations_collide(qualifier: str | None) -> None:
    static = MethodInfo("f", "int", is_static=True)
    nonstatic = MethodInfo("f", "int", is_const=True, ref_qualifier=qualifier)
    assert method_declaration_conflicts([static, nonstatic])


def test_distinct_cv_ref_and_explicit_parameter_overloads_remain_distinct() -> None:
    methods = [
        MethodInfo("f", "int", ref_qualifier="&"),
        MethodInfo("f", "float", ref_qualifier="&&"),
        MethodInfo("f", "int", is_const=True, ref_qualifier="&"),
        MethodInfo("f", "int", is_volatile=True, ref_qualifier="&"),
        MethodInfo("f", "int", is_const=True, is_volatile=True, ref_qualifier="&"),
        MethodInfo("f", "int", parameters=[ParameterInfo("value", "int")]),
    ]
    assert not method_declaration_conflicts(methods)
    assert unique_method_declarations(methods, method_overload_key) == methods


def test_duplicate_observations_ignore_source_locations_and_parameter_names() -> None:
    first = MethodInfo("f", "int", parameters=[ParameterInfo("x", "int")], die_offset=0)
    second = replace(first, parameters=[ParameterInfo("y", "int")], cu_offset=100, die_offset=20)
    assert unique_method_declarations([first, second], method_overload_key) == [first]


@pytest.mark.parametrize(("unsigned", "signed"), [("u8", "s8"), ("uint8_t", "int8_t")])
def test_unsigned_and_signed_alias_names_are_not_speculatively_collapsed(
    unsigned: str, signed: str
) -> None:
    first = ParameterInfo("value", unsigned, type_offset=0)
    second = ParameterInfo("value", signed, type_offset=0)
    assert canonical_parameter_type(first) != canonical_parameter_type(second)


def test_alias_collapse_requires_matching_cu_and_terminal_offset() -> None:
    first = ParameterInfo("value", "MT_CHAR", cu_offset=0, type_offset=16)
    same = ParameterInfo("other", "MT_CTSTR", cu_offset=0, type_offset=16)
    different_cu = ParameterInfo("other", "MT_CTSTR", cu_offset=1, type_offset=16)
    assert canonical_parameter_type(first) == canonical_parameter_type(same)
    assert canonical_parameter_type(first) != canonical_parameter_type(different_cu)


def test_structured_alias_uses_proven_target_not_alias_spelling() -> None:
    integer = TypeReference(TypeDeclarator("int"), kind="DW_TAG_base_type")
    alias = TypeReference(TypeDeclarator("MT_INT"), kind="DW_TAG_typedef", alias_target=integer)
    other = TypeReference(TypeDeclarator("int"), kind="DW_TAG_base_type")
    assert canonical_parameter_type(ParameterInfo("a", "MT_INT", type_reference=alias)) == (
        canonical_parameter_type(ParameterInfo("b", "int", type_reference=other))
    )
    incomplete = replace(alias, alias_target=replace(integer, diagnostics=("missing target",)))
    assert canonical_parameter_type(ParameterInfo("a", "MT_INT", type_reference=incomplete)) != (
        canonical_parameter_type(ParameterInfo("b", "int", type_reference=other))
    )
    array = TypeReference(TypeDeclarator("int", layers=(DeclaratorLayer("array", extent=4),)))
    array_alias = replace(alias, alias_target=array)
    qualified_alias = replace(
        array_alias, declarator=replace(array_alias.declarator, qualifiers=("const",))
    )
    assert canonical_parameter_type(
        ParameterInfo("a", "MT_INT", type_reference=qualified_alias)
    ) != (canonical_parameter_type(ParameterInfo("b", "int", type_reference=array)))


def test_return_alias_equivalence_requires_complete_unqualified_target() -> None:
    integer = TypeReference(TypeDeclarator("int"), kind="DW_TAG_base_type")
    inner = TypeReference(TypeDeclarator("INNER"), kind="DW_TAG_typedef", alias_target=integer)
    outer = TypeReference(TypeDeclarator("OUTER"), kind="DW_TAG_typedef", alias_target=inner)
    direct = MethodInfo("f", "int", return_type_reference=integer)
    aliased = MethodInfo("f", "OUTER", return_type_reference=outer)
    assert canonical_method_signature(direct) == canonical_method_signature(aliased)
    assert not method_declaration_conflicts([direct, aliased])

    missing = replace(outer, alias_target=replace(inner, diagnostics=("incomplete",)))
    qualified = replace(outer, declarator=replace(outer.declarator, qualifiers=("const",)))
    assert method_declaration_conflicts([direct, replace(aliased, return_type_reference=missing)])
    assert method_declaration_conflicts([direct, replace(aliased, return_type_reference=qualified)])


@pytest.mark.parametrize("outer", ["array", "function"])
def test_cxx_parameter_adjustment_matches_pointer_declarator(outer: str) -> None:
    base = TypeReference(TypeDeclarator("int"), kind="DW_TAG_base_type")
    layer = (
        DeclaratorLayer("array", extent=4)
        if outer == "array"
        else DeclaratorLayer("function", parameters=(base,))
    )
    original = TypeReference(TypeDeclarator("int", layers=(layer,)))
    adjusted = TypeReference(
        TypeDeclarator(
            "int",
            layers=(
                (DeclaratorLayer("pointer"),)
                if outer == "array"
                else (DeclaratorLayer("pointer"), layer)
            ),
        )
    )
    first = MethodInfo("f", "void", parameters=[ParameterInfo("a", "raw", type_reference=original)])
    second = MethodInfo(
        "f", "void", parameters=[ParameterInfo("b", "other", type_reference=adjusted)]
    )
    assert method_overload_key(first) == method_overload_key(second)
    assert unique_method_declarations([first, second], method_overload_key) == [first]


def test_nested_array_extent_remains_in_parameter_identity() -> None:
    first = TypeReference(
        TypeDeclarator(
            "int", layers=(DeclaratorLayer("array", extent=3), DeclaratorLayer("array", extent=4))
        )
    )
    second = replace(
        first,
        declarator=replace(
            first.declarator,
            layers=(DeclaratorLayer("array", extent=3), DeclaratorLayer("array", extent=5)),
        ),
    )
    assert canonical_parameter_type(ParameterInfo("a", "int", type_reference=first)) != (
        canonical_parameter_type(ParameterInfo("b", "int", type_reference=second))
    )


def test_structured_callable_identity_takes_precedence_over_raw_spelling() -> None:
    result = TypeReference(TypeDeclarator("int"))
    function = DeclaratorLayer("function", parameters=(result,))
    pointer_to_function = TypeReference(
        TypeDeclarator("void", layers=(DeclaratorLayer("pointer"), function))
    )
    function_returning_pointer = TypeReference(
        TypeDeclarator("void", layers=(function, DeclaratorLayer("pointer")))
    )
    first = MethodInfo(
        "f", "void", parameters=[ParameterInfo("p", "bad text", type_reference=pointer_to_function)]
    )
    same = MethodInfo(
        "f",
        "void",
        parameters=[ParameterInfo("q", "different text", type_reference=pointer_to_function)],
    )
    other = MethodInfo(
        "f",
        "void",
        parameters=[ParameterInfo("p", "bad text", type_reference=function_returning_pointer)],
    )
    assert canonical_method_signature(first) == canonical_method_signature(same)
    assert method_overload_key(first) != method_overload_key(other)


@given(st.permutations([0, 1, 2]))
def test_conflict_detection_does_not_depend_on_observation_order(order: list[int]) -> None:
    methods = [
        MethodInfo("f", "int", ref_qualifier="&"),
        MethodInfo("f", "int", ref_qualifier="&&"),
        MethodInfo("f", "int"),
    ]
    assert method_declaration_conflicts([methods[index] for index in order]) == (
        method_declaration_conflicts(methods)
    )

"""Nested aggregate and callable evidence must participate in dependency closure."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.dependency_extractor import (
    DependencyExtractor,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _aggregate(name: str, **kwargs) -> ClassInfo:
    return ClassInfo(name, 8, [], [], [], [], [], [], **kwargs)


def test_struct_inside_multilevel_nested_class_requires_external_value_header() -> None:
    value = _aggregate("MtColorHLS", die_offset=0)
    inner = _aggregate("Inner", containing_type="Outer::Middle")
    inner.nested_structs = [
        StructInfo("Data", 8, [MemberInfo("color", "MtColorHLS", type_offset=0)])
    ]
    middle = _aggregate("Middle", containing_type="Outer", nested_classes=[inner])
    outer = _aggregate("Outer", nested_classes=[middle])
    headers = HeaderRenderer(Mock()).external_dependency_headers(
        {"Outer": outer, "MtColorHLS": value},
        {"Outer"},
        {"Outer": "Outer.h", "MtColorHLS": "MtColor.h"},
    )
    assert set(headers.values()) == {"MtColor.h"}


def test_callable_closure_includes_owner_enclosure_arguments_and_alias_targets() -> None:
    owner = TypeReference(
        TypeDeclarator("Outer::Owner"),
        die_offset=5,
        kind="DW_TAG_class_type",
        scope=TypeScope((ScopeComponent("Outer", "class", cu_offset=1, die_offset=0),)),
    )
    argument = TypeReference(TypeDeclarator("Argument"), die_offset=6, kind="DW_TAG_class_type")
    callable_type = TypeReference(
        TypeDeclarator(
            "void",
            layers=(
                DeclaratorLayer("member_pointer", owner=owner),
                DeclaratorLayer("function", parameters=(argument,)),
            ),
        ),
        kind="DW_TAG_base_type",
    )
    alias = TypeReference(TypeDeclarator("Callback"), die_offset=7, alias_target=callable_type)
    consumer = _aggregate("Consumer")
    consumer.methods = [
        MethodInfo(
            "bind", "void", parameters=[ParameterInfo("callback", "Callback", type_reference=alias)]
        )
    ]
    extractor = DependencyExtractor(Mock())
    assert extractor.extract_dependencies(consumer) == {0, 5, 6, 7}
    assert extractor.extract_dependencies(consumer, include_method_signatures=False) == set()


def test_inline_struct_references_are_traversed_recursively() -> None:
    leaf = MemberInfo("value", "Value", type_offset=0)
    inner = MemberInfo("inner", "", inline_struct=StructInfo(None, 8, [leaf]))
    outer = MemberInfo("outer", "", inline_struct=StructInfo(None, 8, [inner]))
    consumer = _aggregate("Consumer")
    consumer.members = [outer]
    assert DependencyExtractor(Mock()).extract_dependencies(consumer) == {0}

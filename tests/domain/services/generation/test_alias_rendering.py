"""Alias publication preserves scope, targets, access, and dependency order."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.alias_rendering import (
    AliasDeclarationError,
    external_alias_lines,
    ordered_aliases,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _alias(name, target, scope=None, access=None):
    return TypeReference(
        TypeDeclarator(name),
        kind="DW_TAG_typedef",
        alias_target=target,
        scope=scope if scope is not None else TypeScope(),
        declaration_access=access,
    )


def test_callback_alias_is_inside_owner_before_member_and_keeps_access() -> None:
    owner = TypeReference(TypeDeclarator("Owner"), kind="DW_TAG_class_type")
    target = TypeReference(
        TypeDeclarator(
            "void",
            layers=(
                DeclaratorLayer("member_pointer", owner=owner),
                DeclaratorLayer("function"),
            ),
        )
    )
    alias = _alias(
        "Owner::Callback", target, TypeScope((ScopeComponent("Owner", "class"),)), "private"
    )
    info = ClassInfo(
        "Owner",
        16,
        [MemberInfo("callback", alias.name, type_reference=alias)],
        [],
        [],
        [],
        [],
        [],
        declared_aliases=[alias],
    )
    lookup = Mock()
    lookup.get_die_by_offset.return_value = None
    lookup.find_symbol_offset.return_value = None
    header = HeaderRenderer(lookup).generate_header(info, include_metadata=False)
    assert "private:\n    using Callback = void (Owner::*)();" in header
    assert header.index("using Callback") < header.index("Callback callback;")
    assert "class Callback;" not in header


def test_alias_chain_order_is_independent_of_observation_order() -> None:
    first = _alias("Z", TypeReference(TypeDeclarator("int")))
    second = _alias("A", first)
    assert external_alias_lines([second, first]) == ["using Z = int;", "using A = Z;"]
    assert ordered_aliases([first, second]) == ordered_aliases([second, first])


def test_namespace_alias_and_void_target_are_preserved() -> None:
    alias = _alias(
        "ns::Handle",
        TypeReference(TypeDeclarator("void")),
        TypeScope((ScopeComponent("ns", "namespace"),)),
    )
    assert external_alias_lines([alias]) == ["namespace ns { using Handle = void; }"]


def test_global_alias_is_published_after_actual_aggregate_definition() -> None:
    target = TypeReference(TypeDeclarator("Concrete"), kind="DW_TAG_class_type")
    alias = _alias("ConcreteAlias", target)
    info = ClassInfo("Concrete", 1, [], [], [], [], [], [], source_aliases=(alias,))
    header = HeaderRenderer(Mock()).generate_single_class_header(info, include_metadata=False)
    assert header.index("class Concrete") < header.index("using ConcreteAlias = Concrete;")
    assert "class ConcreteAlias" not in header


def test_alias_conflict_missing_target_and_cycle_fail_explicitly() -> None:
    integer = _alias("A", TypeReference(TypeDeclarator("int")))
    other = replace(integer, alias_target=TypeReference(TypeDeclarator("float")))
    with pytest.raises(AliasDeclarationError, match="conflicting"):
        ordered_aliases([integer, other])
    with pytest.raises(AliasDeclarationError, match="missing alias target"):
        ordered_aliases([replace(integer, alias_target=None)])
    with pytest.raises(AliasDeclarationError, match="cyclic"):
        ordered_aliases([replace(integer, alias_target=TypeReference(TypeDeclarator("A")))])


def test_nested_alias_cannot_be_published_as_a_namespace_or_global_alias() -> None:
    alias = _alias(
        "Owner::A",
        TypeReference(TypeDeclarator("int")),
        TypeScope((ScopeComponent("Owner", "class"),)),
        "public",
    )
    with pytest.raises(AliasDeclarationError, match="enclosing aggregate"):
        external_alias_lines([alias])
    with pytest.raises(AliasDeclarationError, match="incomplete alias evidence"):
        ordered_aliases([replace(alias, scope=TypeScope(complete=False))])


def test_equivalent_observations_deduplicate_without_changing_alias_identity() -> None:
    first = _alias("A", TypeReference(TypeDeclarator("int")))
    second = replace(first, cu_offset=1, die_offset=10)
    assert external_alias_lines([first, second]) == ["using A = int;"]


def test_hierarchy_typedef_uses_referenced_namespace_scope() -> None:
    scope = TypeScope((ScopeComponent("sce", "namespace"), ScopeComponent("Gnm", "namespace")))
    alias = _alias("sce::Gnm::AlignmentType", TypeReference(TypeDeclarator("unsigned int")), scope)
    info = ClassInfo(
        "SizeAlign",
        4,
        [MemberInfo("alignment", alias.name, type_reference=alias)],
        [],
        [],
        [],
        [],
        [],
        qualified_name="sce::Gnm::SizeAlign",
        scope=scope,
    )
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        {"SizeAlign": info}, ["SizeAlign"], "SizeAlign", typedefs={"AlignmentType": "unsigned int"}
    )
    assert "namespace sce::Gnm { using AlignmentType = unsigned int; }" in header
    assert "\ntypedef unsigned int AlignmentType;" not in header
    assert header.index("using AlignmentType") < header.index("class SizeAlign")


def test_single_header_typedef_uses_referenced_namespace_scope() -> None:
    scope = TypeScope((ScopeComponent("nDraw", "namespace"),))
    alias = _alias("nDraw::HIndexBuffer", TypeReference(TypeDeclarator("unsigned char")), scope)
    info = ClassInfo(
        "IndexBuffer",
        1,
        [MemberInfo("handle", alias.name, type_reference=alias)],
        [],
        [],
        [],
        [],
        [],
        qualified_name="nDraw::IndexBuffer",
        scope=scope,
    )
    header = HeaderRenderer(Mock()).generate_header(
        info, typedefs={"HIndexBuffer": "std::uint8_t"}, include_metadata=False
    )
    assert "namespace nDraw { using HIndexBuffer = unsigned char; }" in header
    assert "\ntypedef uint8_t HIndexBuffer;" not in header


def test_namespace_alias_retains_qualified_target_across_namespaces() -> None:
    scope = TypeScope((ScopeComponent("nDraw", "namespace"),))
    target = TypeReference(TypeDeclarator("sce::Gnm::DataFormat"), kind="DW_TAG_class_type")
    alias = _alias("nDraw::GPUFORMAT_TYPE", target, scope)
    info = ClassInfo(
        "View",
        4,
        [MemberInfo("format", alias.name, type_reference=alias)],
        [],
        [],
        [],
        [],
        [],
        qualified_name="nDraw::View",
        scope=scope,
    )
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        {"View": info}, ["View"], "View", typedefs={"GPUFORMAT_TYPE": "DataFormat"}
    )
    assert "namespace nDraw { using GPUFORMAT_TYPE = sce::Gnm::DataFormat; }" in header
    assert "namespace nDraw { typedef DataFormat GPUFORMAT_TYPE; }" not in header


def test_namespace_alias_is_never_forward_declared_as_an_aggregate() -> None:
    scope = TypeScope((ScopeComponent("nDraw", "namespace"),))
    target = TypeReference(TypeDeclarator("nDraw::InputLayouts*"), kind="DW_TAG_pointer_type")
    alias = _alias("nDraw::HInputLayout", target, scope)
    info = ClassInfo(
        "Shader",
        8,
        [MemberInfo("input", alias.name, type_reference=alias)],
        [],
        [],
        [],
        [],
        [],
        qualified_name="nDraw::Shader",
        scope=scope,
    )
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        {"Shader": info}, ["Shader"], "Shader", typedefs={"HInputLayout": "InputLayouts*"}
    )
    assert "namespace nDraw { using HInputLayout = nDraw::InputLayouts*; }" in header
    assert "struct HInputLayout;" not in header
    assert "class HInputLayout;" not in header
    renderer = HeaderRenderer(Mock())._engine._host
    with patch.object(
        renderer,
        "_resolved_forward_declarations",
        return_value={"namespace nDraw { struct HInputLayout; }"},
    ):
        declarations = renderer._hierarchy_forward_declarations(
            {"Shader": info}, ["Shader"], {"HInputLayout": "InputLayouts*"}, True
        )
    assert not any("HInputLayout;" in declaration for declaration in declarations)


def test_same_local_alias_in_distinct_namespaces_does_not_choose_one() -> None:
    left_scope = TypeScope((ScopeComponent("left", "namespace"),))
    right_scope = TypeScope((ScopeComponent("right", "namespace"),))
    left = _alias("left::Handle", TypeReference(TypeDeclarator("unsigned int")), left_scope)
    right = _alias("right::Handle", TypeReference(TypeDeclarator("unsigned int")), right_scope)
    info = ClassInfo(
        "Consumer",
        8,
        [
            MemberInfo("a", left.name, type_reference=left),
            MemberInfo("b", right.name, type_reference=right),
        ],
        [],
        [],
        [],
        [],
        [],
    )
    with pytest.raises(AliasDeclarationError, match="ambiguous alias scope"):
        HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
            {"Consumer": info}, ["Consumer"], "Consumer", typedefs={"Handle": "unsigned int"}
        )

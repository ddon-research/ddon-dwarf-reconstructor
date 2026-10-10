"""Qualified and source-bound header dependency identity regressions."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.header_dependency_names import (
    _resolve_class_name,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_dependency_plan import (
    build_header_name_index,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_hierarchy import (
    HierarchyHeaderGenerationService,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_member_rendering import (
    HeaderMemberRenderingService,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_nested_base_name_lookup_recomputes_after_same_mapping_changes() -> None:
    nested = ClassInfo(
        "Inner",
        4,
        [],
        [],
        [],
        [],
        [],
        [],
        die_offset=0,
        cu_offset=7,
        containing_type="First",
        qualified_name="First::Inner",
    )
    owner = ClassInfo("First", 4, [], [], [], [], [], [], nested_classes=[nested])
    infos = {"First": owner}

    first = HierarchyHeaderGenerationService._qualified_base_type_names(infos)
    nested.qualified_name = "Renamed::Inner"
    nested.containing_type = "Renamed"
    second = HierarchyHeaderGenerationService._qualified_base_type_names(infos)

    assert first == {(7, 0): "First::Inner"}
    assert second == {(7, 0): "Renamed::Inner"}


def test_nested_base_qualification_uses_cu_and_die_identity() -> None:
    left = ClassInfo(
        "Inner",
        4,
        [],
        [],
        [],
        [],
        [],
        [],
        die_offset=0,
        cu_offset=1,
        containing_type="Left",
        qualified_name="Left::Inner",
    )
    right = ClassInfo(
        "Inner",
        4,
        [],
        [],
        [],
        [],
        [],
        [],
        die_offset=0,
        cu_offset=2,
        containing_type="Right",
        qualified_name="Right::Inner",
    )
    index = HierarchyHeaderGenerationService._qualified_base_type_names(
        {"left": left, "right": right}
    )
    renderer = Mock()
    renderer._base_type_names = index
    derived_left = ClassInfo(
        "DerivedLeft",
        8,
        [],
        [],
        ["Inner"],
        [],
        [],
        [],
        cu_offset=1,
        base_class_offsets=[0],
    )
    derived_right = ClassInfo(
        "DerivedRight",
        8,
        [],
        [],
        ["Inner"],
        [],
        [],
        [],
        cu_offset=2,
        base_class_offsets=[0],
    )

    assert index == {(1, 0): "Left::Inner", (2, 0): "Right::Inner"}
    assert HeaderMemberRenderingService._rendered_base_names(renderer, derived_left) == [
        "Left::Inner"
    ]
    assert HeaderMemberRenderingService._rendered_base_names(renderer, derived_right) == [
        "Right::Inner"
    ]


def test_incomplete_cu_cannot_authorize_offset_only_dependency() -> None:
    first = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=0)
    second = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=1, cu_offset=2)
    consumer = ClassInfo(
        "Consumer",
        8,
        [MemberInfo("value", "Node", type_offset=0)],
        [],
        [],
        [],
        [],
        [],
    )
    infos = {"first": first, "second": second, "consumer": consumer}

    assert (
        HeaderRenderer(Mock()).build_dependency_plan(infos, ["consumer"]).dependencies["consumer"]
        == set()
    )


def test_incomplete_cu_cannot_publish_qualified_nested_base_name() -> None:
    nested = ClassInfo(
        "Inner",
        4,
        [],
        [],
        [],
        [],
        [],
        [],
        die_offset=0,
        containing_type="Outer",
        qualified_name="Outer::Inner",
    )

    assert HierarchyHeaderGenerationService._qualified_base_type_names({"nested": nested}) == {}


def test_qualified_dependency_never_binds_to_unrelated_unqualified_name() -> None:
    other = ClassInfo("Leaf", 4, [], [], [], [], [], [], qualified_name="other::Leaf")
    expected = ClassInfo("Leaf", 4, [], [], [], [], [], [], qualified_name="ns::Leaf")
    only_other = build_header_name_index({"other": other})
    both = build_header_name_index({"other": other, "expected": expected})

    assert _resolve_class_name("ns::Leaf*", only_other) is None
    assert _resolve_class_name("ns::Leaf*", both) == "expected"


def test_duplicate_spelling_never_selects_first_source_definition() -> None:
    first = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=10, cu_offset=1)
    second = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=20, cu_offset=2)
    renderer = HeaderRenderer(Mock())
    infos = {"first": first, "second": second}
    index = build_header_name_index(infos)

    assert index.ambiguous["Node"] == ("first", "second")
    assert _resolve_class_name("Node*", index) is None
    assert _resolve_class_name("first", index) == "first"

    consumer = ClassInfo(
        "Consumer",
        8,
        [MemberInfo("value", "Node", type_offset=20, cu_offset=2)],
        [],
        [],
        [],
        [],
        [],
    )
    plan = renderer.build_dependency_plan({**infos, "consumer": consumer}, ["consumer"])
    assert plan.dependencies["consumer"] == {"second"}
    consumer.members[0].type_offset = None
    assert (
        renderer.build_dependency_plan({**infos, "consumer": consumer}, ["consumer"]).dependencies[
            "consumer"
        ]
        == set()
    )

    derived = ClassInfo(
        "Derived",
        8,
        [],
        [],
        ["Node"],
        [],
        [],
        [],
        cu_offset=2,
        base_class_offsets=[20],
    )
    plan = renderer.build_dependency_plan({**infos, "derived": derived}, ["derived"])
    assert plan.dependencies["derived"] == {"second"}
    assert plan.ambiguous_base_requirements == ()

    derived.base_class_offsets.clear()
    unresolved = renderer.build_dependency_plan({**infos, "derived": derived}, ["derived"])
    assert unresolved.dependencies["derived"] == set()
    assert unresolved.ambiguous_base_requirements == (
        "ambiguous complete base requirement for derived (Derived|2|None): "
        "Node candidates first, second; no matching base type DIE",
    )


def test_offset_dependency_uses_target_cu_and_rejects_ambiguous_offsets() -> None:
    left = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=0, cu_offset=1)
    right = ClassInfo("Node", 4, [], [], [], [], [], [], die_offset=0, cu_offset=2)
    reference = TypeReference(TypeDeclarator("unresolved_value"), die_offset=0, cu_offset=2)
    consumer = ClassInfo(
        "Consumer",
        4,
        [
            MemberInfo(
                "value",
                "unresolved_value",
                type_offset=0,
                cu_offset=1,
                type_reference=reference,
            )
        ],
        [],
        [],
        [],
        [],
        [],
    )
    infos = {"left": left, "right": right, "consumer": consumer}
    renderer = HeaderRenderer(Mock())

    assert renderer.build_dependency_plan(infos, ["consumer"]).dependencies["consumer"] == {"right"}
    consumer.members[0].type_reference = None
    consumer.members[0].cu_offset = None
    assert renderer.build_dependency_plan(infos, ["consumer"]).dependencies["consumer"] == set()


def test_nested_pointer_static_and_method_uses_require_evidenced_owner() -> None:
    owner = ClassInfo("Outer", 8, [], [], [], [], [], [], die_offset=10, cu_offset=2)
    scope = TypeScope((ScopeComponent("Outer", "class", cu_offset=2, die_offset=10),))
    nested = TypeReference(
        TypeDeclarator("Outer::Inner", layers=(DeclaratorLayer("pointer"),)),
        die_offset=11,
        cu_offset=2,
        scope=scope,
    )
    consumer = ClassInfo(
        "Consumer",
        8,
        [MemberInfo("ptr", "Outer::Inner*", is_static=True, type_reference=nested)],
        [
            MethodInfo(
                "use",
                "void",
                parameters=[ParameterInfo("item", "Outer::Inner*", type_reference=nested)],
            )
        ],
        [],
        [],
        [],
        [],
    )
    renderer = HeaderRenderer(Mock())
    infos = {"owner": owner, "consumer": consumer}
    assert renderer.build_dependency_plan(infos, ["consumer"]).dependencies["consumer"] == {"owner"}
    assert renderer.build_dependency_plan(infos, ["consumer"]).owner_dependencies["consumer"] == {
        "owner"
    }
    assert renderer.external_dependency_headers(
        infos, {"consumer"}, {"consumer": "Consumer.h", "owner": "Outer.h"}
    ) == {"owner": "Outer.h"}

    consumer.members[0].type_reference = TypeReference(TypeDeclarator("Outer::Inner*"))
    consumer.methods.clear()
    assert renderer.build_dependency_plan(infos, ["consumer"]).dependencies["consumer"] == set()


def test_owner_edge_in_definition_cycle_is_retained_without_invalid_include() -> None:
    scope = TypeScope((ScopeComponent("Outer", "class", cu_offset=1, die_offset=10),))
    nested = TypeReference(TypeDeclarator("Outer::Inner*"), scope=scope)
    owner = ClassInfo(
        "Outer",
        8,
        [MemberInfo("value", "Consumer")],
        [],
        [],
        [],
        [],
        [],
        die_offset=10,
        cu_offset=1,
    )
    consumer = ClassInfo(
        "Consumer",
        8,
        [MemberInfo("ptr", "Outer::Inner*", type_reference=nested)],
        [],
        [],
        [],
        [],
        [],
    )
    infos = {"owner": owner, "consumer": consumer}
    renderer = HeaderRenderer(Mock())
    plan = renderer.build_dependency_plan(infos, ["owner", "consumer"])

    assert plan.owner_dependencies["consumer"] == {"owner"}
    assert plan.unschedulable_owner_cycles == (("consumer", "owner"),)
    assert plan.dependencies["owner"] == {"consumer"}
    assert plan.dependencies["consumer"] == set()
    assert (
        renderer.external_dependency_headers(
            infos, {"consumer"}, {"owner": "Outer.h", "consumer": "Consumer.h"}
        )
        == {}
    )

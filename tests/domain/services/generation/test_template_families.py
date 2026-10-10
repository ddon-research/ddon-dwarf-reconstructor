"""Evidence gates and source-preserving template family projections."""

from dataclasses import replace
from unittest.mock import Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    TemplateTypeParam,
    TemplateValueParam,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.template_declarations import (
    nested_primary_declaration,
    substitute_type,
)
from ddon_dwarf_reconstructor.domain.services.generation.template_families import (
    _signature,
    parameter_declaration,
    plan_template_families,
    template_primary,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _box(argument: str, offset: int = 0) -> ClassInfo:
    return ClassInfo(
        name=f"Box<{argument}>",
        byte_size=16,
        members=[
            MemberInfo("data", f"{argument}*", offset=0),
            MemberInfo("count", "int", offset=8),
        ],
        methods=[MethodInfo("get", f"{argument}*")],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=offset,
        declaration_file="Box.h",
        cu_offset=0,
        template_parameters=[TemplateTypeParam("T", argument, die_offset=offset + 1)],
    )


def _render(infos: dict[str, ClassInfo]) -> str:
    renderer = HeaderRenderer(Mock())
    return renderer.generate_single_file_hierarchy_header(
        infos,
        list(infos),
        next(iter(infos)),
        resolve_forward_declarations=False,
    )


def test_matching_layouts_preserve_explicit_specializations_and_evidence() -> None:
    original = {"a": _box("Apple"), "b": _box("Banana", 10)}
    planned, families = plan_template_families(original, {"a": {"RootA"}, "b": {"RootB"}})
    assert families[0].mode == "explicit"
    assert families[0].origins == ("RootA", "RootB")
    header = _render(planned)
    assert "class Box<Apple>" in header
    assert "class Box<Banana>" in header
    assert "Apple* data;" in header
    assert "Banana* get();" in header
    assert "int count;" in header
    assert "offset: 0x0" in header
    assert original["a"].members[0].type_name == "Apple*"
    assert original["a"].members[0].offset == 0
    assert planned["a"].members[0].offset == 0


def test_family_signature_uses_structured_types_when_raw_names_diverge() -> None:
    first = _box("Apple")
    second = _box("Apple")
    reference = TypeReference(TypeDeclarator("Apple", pointer_depth=1))
    first.members[0].type_reference = reference
    second.members[0].type_reference = reference
    first.methods[0].return_type_reference = reference
    second.methods[0].return_type_reference = reference
    second.members[0].type_name = "stale_member_spelling"
    second.methods[0].return_type = "stale_return_spelling"
    assert _signature(first) == _signature(second)
    second.members[0].type_reference = TypeReference(TypeDeclarator("Banana", pointer_depth=1))
    assert _signature(first) != _signature(second)


def test_single_observation_emits_concrete_explicit_specialization() -> None:
    planned, families = plan_template_families({"a": _box("Apple")}, {})
    assert families[0].mode == "explicit"
    header = _render(planned)
    assert "template <typename T> class Box;" in header
    assert "template <>\nclass Box<Apple>" in header
    assert "Apple* data;  // offset: 0x0" in header


def test_fixed_type_equal_to_argument_does_not_become_a_parameter() -> None:
    infos = {"a": _box("int"), "b": _box("float")}
    _, families = plan_template_families(infos, {})
    assert families[0].mode == "explicit"  # Fixed int count would disagree after substitution.


@pytest.mark.parametrize("missing", [True, False])
def test_missing_signature_or_conflicting_same_specialization_blocks(missing: bool) -> None:
    first = _box("Apple")
    second = replace(first, byte_size=32)
    if missing:
        first = replace(first, template_parameters=[])
        second = first
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "blocked"
    assert families[0].diagnostics
    assert "class Box" not in _render(planned)


def test_interleaved_parameter_order_and_non_type_actual_value() -> None:
    info = replace(
        _box("Apple"),
        template_parameters=[
            TemplateTypeParam("T", "Apple"),
            TemplateValueParam("N", "unsigned int", 9),
            TemplateTypeParam("U", "Banana"),
        ],
    )
    assert parameter_declaration(info) == "template <typename T, unsigned int N, typename U>"
    assert (
        parameter_declaration(replace(info, template_parameters=[TemplateValueParam("N")])) is None
    )


def test_repeated_arguments_and_different_offsets_do_not_generalize() -> None:
    first = _box("Apple")
    second = _box("Banana")
    second.members[0].offset = 4
    assert plan_template_families({"a": first, "b": second}, {})[1][0].mode == "explicit"
    first.template_parameters.append(TemplateTypeParam("U", "Apple"))
    second.template_parameters.append(TemplateTypeParam("U", "Banana"))
    assert plan_template_families({"a": first, "b": second}, {})[1][0].mode == "explicit"


@given(st.integers(min_value=0, max_value=10000))
def test_type_substitution_preserves_qualification_literals_and_indirection(bound: int) -> None:
    expression = f"Outer<const ns::Apple*&, other::Apple, AppleSuffix, int[{bound}]>"
    assert substitute_type(expression, (("ns::Apple", "T"),)) == (
        f"Outer<const T*&, other::Apple, AppleSuffix, int[{bound}]>"
    )


@pytest.mark.parametrize(
    ("name", "primary"),
    [
        ("ns::Box<other::Apple>", "ns::Box"),
        ("Outer<int>::Inner<Apple>", "Outer<int>::Inner"),
        ("Outer<int>::Inner", None),
        ("Broken<Apple", None),
    ],
)
def test_family_scope_respects_template_argument_nesting(name: str, primary: str | None) -> None:
    assert template_primary(name) == primary


def test_distinct_qualified_families_are_not_merged() -> None:
    left = replace(
        _box("Apple"),
        qualified_name="left::Box<Apple>",
        scope=TypeScope((ScopeComponent("left", "namespace"),)),
    )
    right = replace(
        _box("Banana"),
        qualified_name="right::Box<Banana>",
        scope=TypeScope((ScopeComponent("right", "namespace"),)),
    )
    _, families = plan_template_families({"left": left, "right": right}, {})
    assert [family.primary for family in families] == ["left::Box", "right::Box"]
    assert all(family.mode == "explicit" for family in families)


def test_nested_family_is_audited_and_unsupported_scope_is_blocked() -> None:
    child = replace(_box("Apple"), containing_type="Owner", qualified_name="Owner::Box<Apple>")
    parent = replace(_box("Unused"), name="Owner", template_parameters=[], nested_classes=[child])
    projected, families = plan_template_families({"owner": parent}, {"owner": {"Root"}})
    assert families[0].primary == "Owner::Box"
    assert families[0].mode == "blocked"
    assert families[0].origins == ("Root",)
    assert projected["owner"].nested_classes[0].template_rendering.mode == "blocked"


def test_nested_primary_is_declared_only_inside_evidenced_owner() -> None:
    child = replace(
        _box("Apple"),
        containing_type="Owner",
        qualified_name="Owner::Box<Apple>",
        scope=TypeScope((ScopeComponent("Owner", "class", 0, 10),)),
    )
    owner = replace(_box("Unused"), name="Owner", template_parameters=[], nested_classes=[child])
    planned, families = plan_template_families({"owner": owner}, {})
    nested = planned["owner"].nested_classes[0]
    assert families[0].mode == "blocked"
    assert (
        nested_primary_declaration(nested, planned["owner"]) == "template <typename T> class Box;"
    )
    header = _render(planned)
    assert "    template <typename T> class Box;" in header
    assert "// Incomplete template:" in header
    assert "class Box<Apple>" not in header


def test_nested_primary_rejects_unknown_owner_or_conflicting_evidence() -> None:
    child = replace(
        _box("Apple"),
        containing_type="Owner",
        qualified_name="Owner::Box<Apple>",
        scope=TypeScope((ScopeComponent("Owner", "class"),)),
    )
    owner = replace(_box("Unused"), name="Owner", template_parameters=[], nested_classes=[child])
    planned, _ = plan_template_families({"owner": owner}, {})
    nested = planned["owner"].nested_classes[0]
    assert (
        nested_primary_declaration(replace(nested, scope=TypeScope(complete=False)), owner) is None
    )
    assert nested_primary_declaration(replace(nested, containing_type="Other"), owner) is None
    assert (
        nested_primary_declaration(
            replace(nested, template_rendering=replace(nested.template_rendering, primary="Box")),
            owner,
        )
        is None
    )
    conflicting = replace(
        nested,
        template_rendering=replace(
            nested.template_rendering,
            diagnostic="conflicting template specialization: Owner::Box<Apple>",
        ),
    )
    assert nested_primary_declaration(conflicting, owner) is None


def test_specialization_with_different_base_class_die_offsets_is_not_blocked() -> None:
    first = replace(_box("Apple"), base_class_offsets=[0x1000])
    second = replace(_box("Apple"), base_class_offsets=[0x2000])
    _, families = plan_template_families({"first": first, "second": second}, {})
    assert families[0].mode != "blocked"


def test_specialization_with_different_base_classes_is_blocked_as_conflicting() -> None:
    first = replace(_box("Apple"), base_classes=["BaseA"])
    second = replace(_box("Apple"), base_classes=["BaseB"])
    _, families = plan_template_families({"first": first, "second": second}, {})
    assert families[0].mode == "blocked"
    assert any("conflicting template specialization" in d for d in families[0].diagnostics)


def test_distinct_specializations_never_inherit_each_others_methods() -> None:
    first = _box("Apple")
    first = replace(first, methods=[MethodInfo("get", "Apple*")])
    second = _box("Banana", 10)
    second = replace(
        second,
        methods=[
            MethodInfo(
                "set",
                "void",
                parameters=[ParameterInfo("val", "Banana*")],
            )
        ],
    )
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "explicit"
    header = _render(planned)
    assert "Apple* get();" in header
    assert "void set(Banana* val);" in header
    assert planned["a"].methods == first.methods
    assert planned["b"].methods == second.methods


def test_carray_preserves_concrete_element_types_and_extents() -> None:
    first = ClassInfo(
        name="cArray<bool, 8>",
        qualified_name="nDDOUtility::cArray<bool, 8>",
        scope=TypeScope((ScopeComponent("nDDOUtility", "namespace"),)),
        byte_size=8,
        members=[MemberInfo("elems", "bool[8]", offset=0)],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        template_parameters=[
            TemplateTypeParam("T", "bool"),
            TemplateValueParam("N", "unsigned int", 8),
        ],
        declaration_file="nDDOUtility.h",
    )
    second = ClassInfo(
        name="cArray<int, 10>",
        qualified_name="nDDOUtility::cArray<int, 10>",
        scope=TypeScope((ScopeComponent("nDDOUtility", "namespace"),)),
        byte_size=40,
        members=[MemberInfo("elems", "int[10]", offset=0)],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        template_parameters=[
            TemplateTypeParam("T", "int"),
            TemplateValueParam("N", "unsigned int", 10),
        ],
        declaration_file="nDDOUtility.h",
    )
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert len(families) == 1
    assert families[0].mode == "explicit"
    assert families[0].primary == "nDDOUtility::cArray"
    assert planned["a"].template_rendering.representative is True
    assert planned["b"].template_rendering.representative is True
    assert planned["b"].members[0].type_name == "int[10]"
    header = _render(planned)
    assert "template <typename T, unsigned int N>" in header
    assert "class cArray" in header
    assert "bool elems[8];" in header
    assert "int elems[10];" in header
    assert "T elems[N];" not in header
    assert "fill(" not in header
    assert "operator[]" not in header


def test_conflicting_method_returns_block_generic_inference() -> None:
    first = _box("Apple")
    second = _box("Banana", 10)
    first.methods = [MethodInfo("get", "int")]
    second.methods = [MethodInfo("get", "float")]

    planned, families = plan_template_families({"a": first, "b": second}, {})

    assert families[0].mode == "explicit"
    assert families[0].mode != "generic"
    assert planned["a"].methods[0].return_type == "int"


def test_const_qualified_overloads_stay_in_their_specialization() -> None:
    first = _box("Apple")
    second = _box("Banana", 10)
    first.methods = [
        MethodInfo("at", "Apple*", parameters=[ParameterInfo("index", "int")]),
        MethodInfo("at", "const Apple*", parameters=[ParameterInfo("index", "int")], is_const=True),
    ]
    second.methods = [
        MethodInfo("at", "Banana*", parameters=[ParameterInfo("index", "int")]),
        MethodInfo(
            "at", "const Banana*", parameters=[ParameterInfo("index", "int")], is_const=True
        ),
    ]

    planned, families = plan_template_families({"a": first, "b": second}, {})

    assert families[0].mode == "explicit"
    methods = planned["a"].methods
    assert {(method.is_const, method.return_type) for method in methods} == {
        (False, "Apple*"),
        (True, "const Apple*"),
    }


def test_ref_qualified_overloads_remain_distinct() -> None:
    first = _box("Apple")
    second = _box("Banana", 10)
    first.methods = [
        MethodInfo("value", "Apple*", ref_qualifier="&"),
        MethodInfo("value", "Apple*", ref_qualifier="&&"),
    ]
    second.methods = [
        MethodInfo("value", "Banana*", ref_qualifier="&"),
        MethodInfo("value", "Banana*", ref_qualifier="&&"),
    ]

    planned, families = plan_template_families({"a": first, "b": second}, {})

    assert families[0].mode == "explicit"
    assert {method.ref_qualifier for method in planned["a"].methods} == {"&", "&&"}


def test_unrelated_carray_shape_is_not_generalized() -> None:
    first = replace(
        ClassInfo(
            name="cArray<Apple, 2>",
            qualified_name="other::cArray<Apple, 2>",
            scope=TypeScope((ScopeComponent("other", "namespace"),)),
            byte_size=8,
            members=[MemberInfo("elems", "Apple[2]", offset=0)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            template_parameters=[
                TemplateTypeParam("T", "Apple"),
                TemplateValueParam("N", "unsigned int", 2),
            ],
        )
    )
    second = replace(first, name="cArray<Banana, 3>", qualified_name="other::cArray<Banana, 3>")

    _planned, families = plan_template_families({"a": first, "b": second}, {})

    assert families[0].mode == "explicit"


def test_same_specialization_combines_compatible_method_observations_only() -> None:
    first = _box("Apple")
    second = replace(_box("Apple", 10), methods=[MethodInfo("size", "int")])
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "explicit"
    assert {method.name for method in planned["a"].methods} == {"get", "size"}
    assert len(families[0].method_provenance) == 2
    assert first.methods == [MethodInfo("get", "Apple*")]


def test_same_specialization_with_different_field_offsets_is_blocked() -> None:
    first = _box("Apple")
    second = replace(first, members=[replace(member, offset=4) for member in first.members])
    _, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "blocked"


def test_same_spelled_arguments_in_distinct_namespaces_preserve_definitions() -> None:
    first = replace(_box("left::Item"), cu_offset=0)
    second = replace(_box("right::Item"), cu_offset=100)
    planned, families = plan_template_families({"left": first, "right": second}, {})
    assert families[0].mode == "explicit"
    assert families[0].provenance == (("left", 0, 0), ("right", 100, 0))
    header = _render(planned)
    assert header.count("class Box<left::Item>\n") == 1
    assert header.count("class Box<right::Item>\n") == 1
    assert "left::Item* data;" in header
    assert "right::Item* data;" in header


@pytest.mark.parametrize(
    "other",
    [
        MethodInfo("get", "int"),
        MethodInfo("get", "Apple*", is_noexcept=True),
        MethodInfo("get", "Apple*", is_static=True),
        MethodInfo("get", "Apple*", is_virtual=True),
        MethodInfo("get", "Apple*", access="private"),
    ],
)
def test_same_specialization_rejects_declaration_attribute_conflicts(other: MethodInfo) -> None:
    first = _box("Apple")
    second = replace(first, methods=[other], cu_offset=100)
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "blocked"
    assert any("conflicting method declaration" in message for message in families[0].diagnostics)
    assert "class Box" not in _render(planned)


@pytest.mark.parametrize("conflicting", [False, True])
def test_same_qualified_specialization_across_cus_retains_or_rejects_evidence(
    conflicting: bool,
) -> None:
    first = replace(_box("left::Item"), cu_offset=0)
    second = replace(first, cu_offset=100, byte_size=32 if conflicting else first.byte_size)
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].provenance == (("a", 0, 0), ("b", 100, 0))
    if conflicting:
        assert families[0].mode == "blocked"
        assert families[0].diagnostics == ("conflicting template specialization: Box<left::Item>",)
    else:
        assert families[0].mode == "explicit"
        assert _render(planned).count("class Box<left::Item>\n") == 1

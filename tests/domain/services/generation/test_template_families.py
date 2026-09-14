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
    TemplateTypeParam,
    TemplateValueParam,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.template_declarations import (
    substitute_type,
)
from ddon_dwarf_reconstructor.domain.services.generation.template_families import (
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


def test_discriminating_family_renders_one_generic_without_altering_evidence() -> None:
    original = {"a": _box("Apple"), "b": _box("Banana", 10)}
    planned, families = plan_template_families(original, {"a": {"RootA"}, "b": {"RootB"}})
    assert families[0].mode == "generic"
    assert families[0].origins == ("RootA", "RootB")
    header = _render(planned)
    assert header.count("class Box\n") == 1
    assert "T* data;" in header
    assert "T* get();" in header
    assert "int count;" in header
    assert "offset: 0x0" not in header
    assert original["a"].members[0].type_name == "Apple*"
    assert original["a"].members[0].offset == 0
    assert planned["a"].members[0].offset == 0


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
    left = replace(_box("Apple"), qualified_name="left::Box<Apple>")
    right = replace(_box("Banana"), qualified_name="right::Box<Banana>")
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


def test_specialization_with_different_base_class_offsets_is_blocked_as_conflicting() -> None:
    first = replace(_box("Apple"), base_class_offsets=[0])
    second = replace(_box("Apple"), base_class_offsets=[8])
    _, families = plan_template_families({"first": first, "second": second}, {})
    assert families[0].mode == "blocked"
    assert any("conflicting template specialization" in d for d in families[0].diagnostics)

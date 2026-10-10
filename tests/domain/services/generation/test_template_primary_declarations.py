"""Every primary declaration uses the family signature and proven lexical scope."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    TemplateTypeParam,
    TemplateValueParam,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.special_header_renderer import (
    SpecialHeaderRenderer,
)
from ddon_dwarf_reconstructor.domain.services.generation.template_declarations import (
    primary_declaration,
)
from ddon_dwarf_reconstructor.domain.services.generation.template_families import (
    plan_template_families,
)
from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver
from tests.support.type_graph import TypeAttribute, TypeDie

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _value_template(namespace: str, type_name: str, argument: int | bool) -> ClassInfo:
    token = str(argument).lower()
    name = f"Box<{token}>"
    return ClassInfo(
        name,
        1,
        [],
        [],
        [],
        [],
        [],
        [],
        qualified_name=f"{namespace}::{name}",
        scope=TypeScope((ScopeComponent(namespace, "namespace"),)),
        template_parameters=[TemplateValueParam("N", type_name, argument)],
    )


@pytest.mark.parametrize("type_name,argument", [("signed char", -1), ("bool", True), ("short", 4)])
@pytest.mark.parametrize("mode", ["hierarchy", "single", "standalone"])
def test_all_rendering_modes_use_evidenced_parameter_type_and_scope(
    type_name: str,
    argument: int | bool,
    mode: str,
) -> None:
    info = _value_template("left", type_name, argument)
    renderer = HeaderRenderer(Mock())
    if mode == "hierarchy":
        header = renderer.generate_single_file_hierarchy_header(
            {"box": info}, ["box"], "box", resolve_forward_declarations=False
        )
    elif mode == "single":
        header = renderer.generate_header(info, include_metadata=False)
    else:
        header = renderer.generate_single_class_header(info, include_metadata=False)
    assert f"namespace left {{ template <{type_name} N> class Box; }}" in header
    assert "template <unsigned int" not in header
    assert f"template <>\nclass {info.name}\n" in header
    assert "class left::Box" not in header


def test_same_named_primaries_keep_different_namespace_signatures() -> None:
    infos = {
        "left": _value_template("left", "bool", True),
        "right": _value_template("right", "short", -1),
    }
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        infos, list(infos), "left", resolve_forward_declarations=False
    )
    assert "namespace left { template <bool N> class Box; }" in header
    assert "namespace right { template <short N> class Box; }" in header
    assert "class Box<true>" in header and "class Box<-1>" in header


def test_primary_parameter_names_may_differ_between_cu_observations() -> None:
    first = _value_template("left", "short", -1)
    second = replace(first, template_parameters=[TemplateValueParam("Other", "short", -1)])
    planned, families = plan_template_families({"a": first, "b": second}, {})
    assert families[0].mode == "explicit"
    assert primary_declaration(planned["a"]) == primary_declaration(planned["b"])


@pytest.mark.parametrize(
    "scope", [None, TypeScope(complete=False), TypeScope((ScopeComponent("left", "class"),))]
)
def test_unknown_or_aggregate_scope_never_relocates_primary(scope: TypeScope | None) -> None:
    info = replace(_value_template("left", "short", -1), scope=scope)
    planned, families = plan_template_families({"box": info}, {})
    assert families[0].mode == "blocked"
    assert any("primary scope" in diagnostic for diagnostic in families[0].diagnostics)
    assert primary_declaration(planned["box"]) is None


def test_parameter_kind_or_type_disagreement_blocks_primary() -> None:
    first = _value_template("left", "short", -1)
    for parameters in ([TemplateValueParam("N", "bool", True)], [TemplateTypeParam("N", "int")]):
        second = replace(first, template_parameters=parameters)
        planned, families = plan_template_families({"a": first, "b": second}, {})
        assert families[0].mode == "blocked"
        assert primary_declaration(planned["a"]) is None


def _namespace() -> TypeDie:
    namespace = TypeDie("DW_TAG_namespace", 100).named("left")
    child = TypeDie("DW_TAG_class_type", 10, parent=namespace).named("Box<-1>")
    base = TypeDie("DW_TAG_base_type", 20).named("signed char")
    parameter = TypeDie("DW_TAG_template_value_param", 30, parent=child).named("N").link(base)
    parameter.attributes["DW_AT_const_value"] = TypeAttribute(-1, "DW_FORM_sdata")
    child.children = [parameter]
    namespace.children = [child]
    return namespace


def test_namespace_primary_uses_real_child_parameter_evidence() -> None:
    namespace = _namespace()
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    parser.parse_class_info = Mock(
        side_effect=AssertionError("namespace forward must not parse a full class")
    )
    header = SpecialHeaderRenderer.render_namespace("left", namespace.cu, namespace, parser)
    assert "namespace left { template <signed char N> class Box; }" in header
    assert "Unresolved template" not in header
    assert "class Box<-1>;" not in header


def test_namespace_declaration_projection_is_not_cached_as_complete_definition() -> None:
    namespace = _namespace()
    child = namespace.children[0]
    base = TypeDie("DW_TAG_base_type", 80).named("int")
    member = TypeDie("DW_TAG_member", 70, parent=child).named("value").link(base)
    member.attributes["DW_AT_data_member_location"] = TypeAttribute(0, "DW_FORM_data1")
    child.children.append(member)
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    declaration = parser.parse_template_declaration_info(namespace.cu, child)
    assert declaration.is_declaration and not declaration.members
    complete = parser.parse_class_info(namespace.cu, child)
    assert not complete.is_declaration
    assert [item.name for item in complete.members] == ["value"]


def test_namespace_qualified_templates_have_distinct_include_guards() -> None:
    renderer = HeaderRenderer(Mock())
    headers = [
        renderer.generate_single_class_header(_value_template(namespace, "short", -1))
        for namespace in ("left", "right")
    ]
    assert headers[0].splitlines()[0] != headers[1].splitlines()[0]


def test_namespace_conflicting_signatures_are_diagnosed_without_selecting_one() -> None:
    namespace = _namespace()
    duplicate = _namespace().children[0]
    duplicate.offset = 40
    duplicate.parent = namespace
    duplicate.children[0].offset = 60
    duplicate.children[0].link(TypeDie("DW_TAG_base_type", 50).named("bool"))
    namespace.children.append(duplicate)
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    header = SpecialHeaderRenderer.render_namespace("left", namespace.cu, namespace, parser)
    assert "unresolved template parameter signature: left::Box" in header
    assert "template <" not in header


def test_namespace_primary_without_specialization_spelling_uses_parameter_dies() -> None:
    namespace = _namespace()
    child = namespace.children[0].named("Box")
    del child.children[0].attributes["DW_AT_const_value"]
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    header = SpecialHeaderRenderer.render_namespace("left", namespace.cu, namespace, parser)
    assert "namespace left { template <signed char N> class Box; }" in header
    assert "\nclass Box;" not in header


def test_namespace_parameter_lookup_failure_does_not_publish_a_partial_header() -> None:
    namespace = _namespace()
    parser = Mock()
    parser.parse_template_declaration_info.side_effect = RuntimeError("incomplete children")
    with pytest.raises(RuntimeError, match="incomplete children"):
        SpecialHeaderRenderer.render_namespace("left", namespace.cu, namespace, parser)


def test_known_dependency_primary_uses_qualified_evidence() -> None:
    template = _value_template("left", "short", -1)
    consumer = ClassInfo("Consumer", 8, [MemberInfo("box", "left::Box<-1>*")], [], [], [], [], [])
    planned, _ = plan_template_families({"box": template}, {})
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        {"consumer": consumer},
        ["consumer"],
        "consumer",
        base_type_infos=planned,
        resolve_forward_declarations=False,
    )
    assert "namespace left { template <short N> class Box; }" in header

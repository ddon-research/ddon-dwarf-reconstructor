"""Each published definition keeps its own proven lexical namespace."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators.symbol_header_validation import (
    complete_definition_names,
    validate_rendered_headers,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo
from ddon_dwarf_reconstructor.domain.models.dwarf.template_rendering import TemplateRendering
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.header_type_planning import (
    HeaderTypePlanningService,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _value(namespace: str | None) -> ClassInfo:
    scope = TypeScope((ScopeComponent(namespace, "namespace"),)) if namespace else TypeScope()
    return ClassInfo(
        "Value", 1, [], [], [], [], [], [], scope=scope, qualified_name=scope.qualify("Value")
    )


def test_mixed_global_and_namespace_definitions_have_distinct_identities() -> None:
    infos = {"global": _value(None), "left": _value("left"), "right": _value("right")}
    renderer = HeaderRenderer(Mock())
    header = renderer.generate_single_file_hierarchy_header(
        infos,
        list(infos),
        "global",
        resolve_forward_declarations=False,
    )
    assert set(complete_definition_names(header)) == {"Value", "left::Value", "right::Value"}
    assert "using left::Value;" not in header
    assert "using right::Value;" not in header
    validate_rendered_headers(
        {"mixed.h": header},
        {"mixed.h": ("shared", tuple(infos))},
        infos,
        {key: "shared" for key in infos},
    )


def test_forward_declaration_identity_includes_proven_namespace() -> None:
    assert (
        HeaderTypePlanningService._forward_declaration_name(
            "namespace left::detail { struct Value; }"
        )
        == "left::detail::Value"
    )


def test_validation_ignores_scope_text_inside_comments_and_literals() -> None:
    code = """
// namespace false_scope { class Wrong { };
namespace actual {
/* class Wrong { */
struct Value { static constexpr auto label = "namespace false_scope { class Wrong {"; };
}
"""
    assert complete_definition_names(code) == ["actual::Value"]


def test_generic_definition_deduplication_retains_qualified_primary_identity() -> None:
    infos = {"left": _value("left"), "right": _value("right")}
    for namespace, info in infos.items():
        info.template_rendering = TemplateRendering(
            f"{namespace}::Value", "template <typename T>", "generic"
        )
    header = HeaderRenderer(Mock()).generate_single_file_hierarchy_header(
        infos, list(infos), "left", resolve_forward_declarations=False
    )
    assert set(complete_definition_names(header)) == {"left::Value", "right::Value"}

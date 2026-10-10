"""Namespace enums retain source identity and gain complete publication headers."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators.symbol_enum_publication import (
    EnumPublicationError,
    plan_namespace_enums,
)
from ddon_dwarf_reconstructor.application.generators.symbol_method_diagnostics import (
    method_signature_diagnostics,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MethodInfo,
    ParameterInfo,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import TypeDeclarator
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _consumer(offset: int, *, unit: int = 0) -> ClassInfo:
    enum = TypeReference(
        TypeDeclarator("nDraw::PASS_TYPE"),
        cu_offset=unit,
        die_offset=offset,
        kind="DW_TAG_enumeration_type",
    )
    parameter = ParameterInfo("pass_type", enum.name, type_reference=enum)
    return ClassInfo(
        "Consumer", 8, [], [MethodInfo("setPass", "void", parameters=[parameter])], [], [], [], []
    )


def _enum(offset: int, *, unit: int = 0, value: int = 1) -> EnumInfo:
    return EnumInfo(
        "PASS_TYPE",
        4,
        [EnumeratorInfo("PASS_BEGIN", value)],
        scoped=False,
        fixed_base_evidence=False,
        cu_offset=unit,
        die_offset=offset,
        scope=TypeScope((ScopeComponent("nDraw", "namespace"),)),
    )


def test_namespace_enum_publication_has_complete_definition_and_exact_origin() -> None:
    context = Mock()
    context.class_parser._find_die_and_cu_by_offset.return_value = (
        Mock(cu_offset=0),
        Mock(tag="DW_TAG_enumeration_type"),
    )
    context.class_parser.parse_enum.return_value = _enum(0)

    plan = plan_namespace_enums(context, {"owner": _consumer(0)}, {"owner": {"Root"}})

    assert len(plan.headers) == 1
    path, content = next(iter(plan.headers.items()))
    assert path.startswith("shared/nDraw-enums-")
    assert "namespace nDraw {\n\nenum PASS_TYPE\n{\n    PASS_BEGIN = 1\n};" in content
    assert plan.paths_by_class == {"owner": {"nDraw::PASS_TYPE": path}}
    assert plan.identities_by_header[path] == ("nDraw::PASS_TYPE|0|0",)
    assert plan.origins_by_identity == {"nDraw::PASS_TYPE|0|0": ("Root",)}
    assert plan.paths_by_namespace == {"nDraw": path}
    assert plan.enums_by_namespace == {
        "nDraw": {"PASS_TYPE": context.class_parser.parse_enum.return_value}
    }
    assert (
        method_signature_diagnostics({"owner": _consumer(0)}, known_enums=plan.qualified_names)
        == ()
    )


def test_conflicting_same_named_enums_from_two_units_fail_closed() -> None:
    context = Mock()
    context.class_parser._find_die_and_cu_by_offset.side_effect = [
        (Mock(cu_offset=0), Mock(tag="DW_TAG_enumeration_type")),
        (Mock(cu_offset=1), Mock(tag="DW_TAG_enumeration_type")),
    ]
    context.class_parser.parse_enum.side_effect = [_enum(4), _enum(5, unit=1, value=2)]
    infos = {"first": _consumer(4), "second": _consumer(5, unit=1)}
    with pytest.raises(EnumPublicationError, match="Conflicting namespace enum definitions"):
        plan_namespace_enums(context, infos, {"first": {"A"}, "second": {"B"}})


def test_enum_source_mismatch_fails_before_publication() -> None:
    context = Mock()
    context.class_parser._find_die_and_cu_by_offset.return_value = (
        Mock(cu_offset=9),
        Mock(tag="DW_TAG_enumeration_type"),
    )
    with pytest.raises(EnumPublicationError, match="Enum source mismatch"):
        plan_namespace_enums(context, {"owner": _consumer(0)}, {"owner": {"Root"}})

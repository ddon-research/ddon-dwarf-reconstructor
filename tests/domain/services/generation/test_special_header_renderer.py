"""Tests for special-case header rendering."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import EnumeratorInfo, EnumInfo
from ddon_dwarf_reconstructor.domain.services.generation.special_header_renderer import (
    SpecialHeaderRenderer,
)


@pytest.mark.unit
def test_not_found_header_is_deterministic() -> None:
    header = SpecialHeaderRenderer.render_not_found("MissingType")

    assert header.startswith(
        "#ifndef DDON_MISSINGTYPE_7D1B03A1B3BF43E4_H\n#define DDON_MISSINGTYPE_7D1B03A1B3BF43E4_H"
    )
    assert "Class 'MissingType' not found" in header
    assert header.endswith("#endif // DDON_MISSINGTYPE_7D1B03A1B3BF43E4_H\n")


@pytest.mark.unit
def test_namespace_children_are_filtered_and_sorted() -> None:
    class_child = Mock(tag="DW_TAG_class_type")
    class_child.attributes = {"DW_AT_name": Mock(value=b"Zulu")}
    struct_child = Mock(tag="DW_TAG_structure_type")
    struct_child.attributes = {"DW_AT_name": Mock(value="Alpha")}
    ignored_child = Mock(tag="DW_TAG_variable")
    ignored_child.attributes = {"DW_AT_name": Mock(value=b"ignored")}
    namespace_die = Mock(offset=0x1234)
    namespace_die.attributes = {}
    namespace_die.iter_children.return_value = [class_child, ignored_child, struct_child]
    cu = Mock(cu_offset=0x20)

    header = SpecialHeaderRenderer.render_namespace("game::layout", cu, namespace_die)

    assert "#ifndef DDON_GAME_LAYOUT_666AD82A3528573F_NAMESPACE_H" in header
    assert "// Contains 2 type(s)" in header
    assert header.index("struct Alpha;") < header.index("class Zulu;")
    assert "ignored" not in header


@pytest.mark.unit
def test_empty_namespace_is_explicit() -> None:
    namespace_die = Mock(offset=1)
    namespace_die.attributes = {}
    namespace_die.iter_children.return_value = []

    header = SpecialHeaderRenderer.render_namespace("empty", Mock(cu_offset=2), namespace_die)

    assert "// No classes found in this namespace" in header


@pytest.mark.unit
@pytest.mark.regression
def test_namespace_renders_source_parsed_complete_unscoped_enum() -> None:
    enum_die = Mock(tag="DW_TAG_enumeration_type", offset=0)
    enum_die.attributes = {"DW_AT_name": Mock(value=b"PASS_TYPE")}
    namespace_die = Mock(offset=12)
    namespace_die.attributes = {}
    namespace_die.iter_children.return_value = [enum_die]
    parser = Mock()
    parser.parse_enum.return_value = EnumInfo(
        "PASS_TYPE",
        4,
        [EnumeratorInfo("PASS_BEGIN", 1), EnumeratorInfo("PASS_END", 2)],
        scoped=False,
        fixed_base_evidence=False,
        cu_offset=0,
        die_offset=0,
    )

    header = SpecialHeaderRenderer.render_namespace(
        "nDraw", Mock(cu_offset=0), namespace_die, parser
    )

    assert "// Contains 1 type(s)" in header
    assert "enum PASS_TYPE\n{\n    PASS_BEGIN = 1,\n    PASS_END = 2\n};" in header
    assert "enum class PASS_TYPE" not in header
    parser.parse_enum.assert_called_once_with(enum_die)


@pytest.mark.unit
@pytest.mark.regression
def test_namespace_uses_published_enum_header_once() -> None:
    enum_die = Mock(tag="DW_TAG_enumeration_type", offset=7, attributes={})
    namespace_die = Mock(offset=12, attributes={})
    namespace_die.iter_children.return_value = [enum_die]
    parser = Mock()
    parser.parse_enum.return_value = EnumInfo(
        "PASS_TYPE", 4, [EnumeratorInfo("PASS_BEGIN", 1)], scoped=False
    )

    header = SpecialHeaderRenderer.render_namespace(
        "nDraw",
        Mock(cu_offset=0),
        namespace_die,
        parser,
        external_enum_include="../shared/nDraw-enums.h",
        external_enums={"PASS_TYPE": parser.parse_enum.return_value},
    )

    assert '#include "../shared/nDraw-enums.h"' in header
    assert "enum PASS_TYPE" not in header

    with pytest.raises(ValueError, match="Conflicting published namespace enum"):
        SpecialHeaderRenderer.render_namespace(
            "nDraw",
            Mock(cu_offset=0),
            namespace_die,
            parser,
            external_enum_include="../shared/nDraw-enums.h",
            external_enums={"PASS_TYPE": EnumInfo("PASS_TYPE", 4, [], scoped=False)},
        )


@pytest.mark.unit
@pytest.mark.regression
def test_namespace_enum_requires_a_parser_and_known_scopedness() -> None:
    enum_die = Mock(tag="DW_TAG_enumeration_type", offset=23)
    enum_die.attributes = {"DW_AT_name": Mock(value=b"Mode")}
    namespace_die = Mock(offset=12)
    namespace_die.attributes = {}
    namespace_die.iter_children.return_value = [enum_die]
    with pytest.raises(ValueError, match="Enum parser unavailable"):
        SpecialHeaderRenderer.render_namespace("game", Mock(cu_offset=0), namespace_die)

    parser = Mock()
    parser.parse_enum.return_value = EnumInfo("Mode", 4, [], scoped=None, die_offset=23)
    with pytest.raises(ValueError, match="unknown enum scopedness"):
        SpecialHeaderRenderer.render_namespace("game", Mock(cu_offset=0), namespace_die, parser)


@pytest.mark.unit
@pytest.mark.regression
def test_namespace_enum_declaration_flag_and_conflicting_definitions() -> None:
    first = Mock(tag="DW_TAG_enumeration_type", offset=2)
    first.attributes = {"DW_AT_declaration": Mock(value=False)}
    second = Mock(tag="DW_TAG_enumeration_type", offset=3)
    second.attributes = {}
    namespace_die = Mock(offset=1)
    namespace_die.attributes = {}
    namespace_die.iter_children.return_value = [first, second]
    parser = Mock()
    parser.parse_enum.side_effect = [
        EnumInfo("Mode", 4, [EnumeratorInfo("One", 1)], scoped=False),
        EnumInfo("Mode", 4, [EnumeratorInfo("Two", 2)], scoped=False),
    ]
    with pytest.raises(ValueError, match="Conflicting namespace enum definitions"):
        SpecialHeaderRenderer.render_namespace("game", Mock(cu_offset=0), namespace_die, parser)
    assert parser.parse_enum.call_count == 2

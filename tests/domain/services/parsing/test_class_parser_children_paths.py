"""Direct-child traversal tests for all supported DWARF child categories."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    StructInfo,
    TemplateTypeParam,
    TemplateValueParam,
    UnionInfo,
)
from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser


def _parser() -> ClassParser:
    parser = object.__new__(ClassParser)
    parser.type_resolver = Mock()
    parser.parse_member = Mock(return_value=MemberInfo("field", "u32"))
    parser.parse_method = Mock(return_value=MethodInfo("run", "void"))
    parser.parse_enum = Mock(return_value=EnumInfo("Mode", 4, []))
    parser.parse_class_info = Mock(return_value=ClassInfo("Nested", 1, [], [], [], [], [], []))
    parser.parse_nested_structure = Mock(return_value=StructInfo("Inner", 4, [], 0x10))
    parser.parse_union = Mock(return_value=UnionInfo("Choice", 4, [], [], 0x20))
    parser.parse_template_type_param = Mock(return_value=TemplateTypeParam("T"))
    parser.parse_template_value_param = Mock(return_value=TemplateValueParam("N", "int", 1))
    parser._parse_member_or_anonymous = Mock(side_effect=lambda *_args: MemberInfo("field", "u32"))
    parser._get_accessibility = Mock(return_value="public")
    parser._find_class_full_scan = Mock()
    return parser


def _die(tag: str, offset: int) -> Mock:
    die = Mock(tag=tag, offset=offset)
    die.attributes = {}
    return die


@pytest.mark.unit
def test_parse_class_children_collects_supported_direct_children() -> None:
    parser = _parser()
    inheritance = _die("DW_TAG_inheritance", 1)
    member = _die("DW_TAG_member", 2)
    method = _die("DW_TAG_subprogram", 3)
    enum = _die("DW_TAG_enumeration_type", 4)
    nested_class = _die("DW_TAG_class_type", 5)
    nested_struct = _die("DW_TAG_structure_type", 6)
    nested_union = _die("DW_TAG_union_type", 7)
    type_param = _die("DW_TAG_template_type_param", 8)
    value_param = _die("DW_TAG_template_value_param", 9)
    class_die = _die("DW_TAG_class_type", 0)
    class_die.iter_children.return_value = [
        member,
        method,
        inheritance,
        enum,
        nested_class,
        nested_struct,
        nested_union,
        type_param,
        value_param,
        _die("DW_TAG_typedef", 10),
    ]
    parser.type_resolver.resolve_type_name.return_value = "Base"

    result = parser._parse_class_children(Mock(), class_die, "Owner")

    assert len(result.members) == 1
    assert len(result.methods) == 1
    assert result.base_classes == ["Base"]
    assert len(result.enums) == 1
    assert len(result.nested_classes) == 1
    assert len(result.nested_structs) == 1
    assert len(result.unions) == 1
    assert result.template_type_params == [TemplateTypeParam("T")]
    assert result.template_value_params == [TemplateValueParam("N", "int", 1)]


@pytest.mark.unit
def test_parse_class_children_skips_unknown_or_unresolved_children() -> None:
    parser = _parser()
    parser._parse_member_or_anonymous.return_value = None
    parser.parse_method.return_value = None
    parser.parse_enum.return_value = None
    parser.parse_class_info.return_value = None
    parser.parse_nested_structure.return_value = None
    parser.parse_union.return_value = None
    parser.parse_template_type_param.return_value = None
    parser.parse_template_value_param.return_value = None
    parser.type_resolver.resolve_type_name.return_value = "unknown_type"
    unknown = _die("DW_TAG_subprogram", 1)
    class_die = _die("DW_TAG_class_type", 0)
    class_die.iter_children.return_value = [
        unknown,
        _die("DW_TAG_inheritance", 2),
        _die("DW_TAG_structure_type", 3),
    ]

    result = parser._parse_class_children(Mock(), class_die, "Owner")

    assert result.members == []
    assert result.methods == []
    assert result.base_classes == []
    assert result.nested_structs == []


@pytest.mark.unit
def test_append_union_child_deduplicates_offsets() -> None:
    parser = _parser()
    state = Mock()
    state.unions = []
    processed: set[int] = {7}
    child = _die("DW_TAG_union_type", 7)

    parser._append_union_child(child, processed, state)

    assert state.unions == []
    parser._append_union_child(_die("DW_TAG_union_type", 8), processed, state)
    assert len(state.unions) == 1

"""Aggregate, enum, and declaration-file parser coverage."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import MemberInfo, StructInfo
from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser


def _parser() -> ClassParser:
    parser = object.__new__(ClassParser)
    parser.type_resolver = Mock()
    parser.dwarf_info = Mock()
    return parser


def _die(tag: str, offset: int = 1, attributes: dict[str, Mock] | None = None) -> Mock:
    die = Mock(tag=tag, offset=offset)
    die.attributes = attributes or {}
    die.iter_children.return_value = []
    return die


def _attr(value: object, form: str = "") -> Mock:
    return Mock(value=value, form=form)


@pytest.mark.unit
def test_parse_enum_handles_integer_bytes_and_invalid_values() -> None:
    parser = _parser()
    enum = _die(
        "DW_TAG_enumeration_type",
        attributes={"DW_AT_name": _attr(b"Mode"), "DW_AT_byte_size": _attr(1)},
    )
    enum.iter_children.return_value = [
        _die(
            "DW_TAG_enumerator",
            attributes={"DW_AT_name": _attr(b"Zero"), "DW_AT_const_value": _attr(0)},
        ),
        _die(
            "DW_TAG_enumerator",
            attributes={"DW_AT_name": _attr(b"Minus"), "DW_AT_const_value": _attr(b"\xff")},
        ),
        _die(
            "DW_TAG_enumerator",
            attributes={"DW_AT_name": _attr(b"Bad"), "DW_AT_const_value": _attr("bad")},
        ),
        _die("DW_TAG_enumerator", attributes={"DW_AT_name": _attr(b"Missing")}),
    ]

    result = parser.parse_enum(enum)

    assert result is not None
    assert result.name == "Mode"
    assert [(item.name, item.value) for item in result.enumerators] == [
        ("Zero", 0),
        ("Minus", -1),
    ]


@pytest.mark.unit
def test_parse_enum_accepts_exact_decimal_values_from_analytical_rows() -> None:
    parser = _parser()
    enum = _die(
        "DW_TAG_enumeration_type",
        offset=0x100,
        attributes={"DW_AT_name": _attr(b"ValueType"), "DW_AT_byte_size": _attr(4)},
    )
    enum.iter_children.return_value = [
        _die(
            "DW_TAG_enumerator",
            offset=0x110,
            attributes={
                "DW_AT_name": _attr(b"VTYPE_F64"),
                "DW_AT_const_value": _attr(Decimal("8"), "DW_FORM_sdata"),
            },
        )
    ]

    result = parser.parse_enum(enum)

    assert result is not None
    assert [(item.name, item.value) for item in result.enumerators] == [("VTYPE_F64", 8)]


@pytest.mark.unit
def test_parse_enum_uses_referenced_unsigned_base_type_and_width() -> None:
    parser = _parser()
    enum = _die(
        "DW_TAG_enumeration_type",
        attributes={"DW_AT_name": _attr(b"ByteValue"), "DW_AT_byte_size": _attr(1)},
    )
    unsigned_type = _die(
        "DW_TAG_base_type",
        attributes={"DW_AT_encoding": _attr(0x07)},
    )
    enum.attributes["DW_AT_type"] = _attr(0x200)
    enum.get_DIE_from_attribute.return_value = unsigned_type
    enum.iter_children.return_value = [
        _die(
            "DW_TAG_enumerator",
            attributes={
                "DW_AT_name": _attr(b"Max"),
                "DW_AT_const_value": _attr(255, "DW_FORM_udata"),
            },
        ),
        _die(
            "DW_TAG_enumerator",
            attributes={
                "DW_AT_name": _attr(b"TooWide"),
                "DW_AT_const_value": _attr(256, "DW_FORM_udata"),
            },
        ),
    ]

    result = parser.parse_enum(enum)

    assert result is not None
    assert [(item.name, item.value) for item in result.enumerators] == [("Max", 255)]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_value", "form", "byte_size", "expected"),
    [
        (-128, "DW_FORM_sdata", 1, -128),
        (127, "DW_FORM_sdata", 1, 127),
        (128, "DW_FORM_sdata", 1, None),
        (-1, "DW_FORM_udata", 1, None),
        ("42", "DW_FORM_data4", 4, 42),
        (1.5, "DW_FORM_sdata", 4, None),
    ],
)
def test_enumerator_value_respects_form_and_declared_width(
    raw_value: object, form: str, byte_size: int, expected: int | None
) -> None:
    assert (
        ClassParser._enumerator_value(
            raw_value,
            form=form,
            byte_size=byte_size,
        )
        == expected
    )


@pytest.mark.unit
def test_parse_enum_defaults_missing_name_and_size() -> None:
    parser = _parser()
    enum = _die("DW_TAG_enumeration_type")
    enum.iter_children.return_value = [_die("DW_TAG_enumerator", attributes={})]

    result = parser.parse_enum(enum)

    assert result is not None
    assert result.name == "unknown_enum"
    assert result.byte_size == 4
    assert result.enumerators == []


@pytest.mark.unit
def test_parse_nested_structure_and_union_collect_members() -> None:
    parser = _parser()
    member = _die("DW_TAG_member", offset=0x20)
    parsed_member = MemberInfo("field", "u32", offset=0)
    parser.parse_member = Mock(return_value=parsed_member)
    nested = _die(
        "DW_TAG_structure_type",
        offset=0x30,
        attributes={"DW_AT_name": _attr(b"Nested"), "DW_AT_byte_size": _attr(4)},
    )
    nested.iter_children.return_value = [member]

    struct = parser.parse_nested_structure(nested)

    assert struct == StructInfo("Nested", 4, [parsed_member], 0x30)
    union = _die(
        "DW_TAG_union_type",
        offset=0x40,
        attributes={"DW_AT_name": _attr(b"Choice"), "DW_AT_byte_size": _attr(8)},
    )
    union.iter_children.return_value = [member, nested]

    union_info = parser.parse_union(union)

    assert union_info is not None
    assert union_info.name == "Choice"
    assert union_info.byte_size == 8
    assert union_info.members == [parsed_member]
    assert union_info.nested_structs == [struct]


@pytest.mark.unit
def test_parse_anonymous_aggregate_uses_empty_name_and_zero_size() -> None:
    parser = _parser()
    parser.parse_member = Mock(return_value=None)
    struct = _die("DW_TAG_structure_type", offset=0x50)
    union = _die("DW_TAG_union_type", offset=0x60)

    assert parser.parse_nested_structure(struct).name is None
    assert parser.parse_nested_structure(struct).byte_size == 0
    assert parser.parse_union(union).name == ""
    assert parser.parse_union(union).byte_size == 0


@pytest.mark.unit
def test_parse_member_preserves_anonymous_inline_class_members() -> None:
    parser = _parser()
    inline = StructInfo(
        name=None,
        byte_size=4,
        members=[MemberInfo("flag", "uint32_t", offset=0, bit_size=1)],
        die_offset=0x80,
    )
    parser.parse_nested_structure = Mock(return_value=inline)
    member = _die(
        "DW_TAG_member",
        offset=0x70,
        attributes={"DW_AT_name": _attr(b"m_bits"), "DW_AT_type": _attr(0x80)},
    )
    anonymous_class = _die(
        "DW_TAG_class_type",
        offset=0x80,
        attributes={"DW_AT_byte_size": _attr(4)},
    )
    member.get_DIE_from_attribute.return_value = anonymous_class
    parser.type_resolver.resolve_type_name.return_value = "class_type"

    result = parser.parse_member(member)

    assert result is not None
    assert result.type_name == "anonymous_struct"
    assert result.inline_struct is inline


@pytest.mark.unit
def test_declaration_file_handles_valid_missing_and_broken_line_programs() -> None:
    parser = _parser()
    cu = Mock()
    file_entry = Mock()
    file_entry.name = b"include/MtObject.h"
    line_program = Mock()
    line_program.header.file_entry = [file_entry]
    parser.dwarf_info.line_program_for_CU.return_value = line_program

    assert parser._get_declaration_file(
        cu, _die("x", attributes={"DW_AT_decl_file": _attr(1)})
    ) == ("include/MtObject.h")
    assert parser._get_declaration_file(cu, _die("x")) is None
    assert (
        parser._get_declaration_file(cu, _die("x", attributes={"DW_AT_decl_file": _attr(2)}))
        is None
    )

    parser.dwarf_info.line_program_for_CU.side_effect = RuntimeError("broken")
    assert (
        parser._get_declaration_file(cu, _die("x", attributes={"DW_AT_decl_file": _attr(1)}))
        is None
    )

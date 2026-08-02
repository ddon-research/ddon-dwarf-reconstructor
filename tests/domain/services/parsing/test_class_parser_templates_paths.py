"""Template and inheritance parser branch coverage."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser


def _parser() -> ClassParser:
    parser = object.__new__(ClassParser)
    parser.type_resolver = Mock()
    return parser


def _die(tag: str, attributes: dict[str, Mock] | None = None) -> Mock:
    die = Mock(tag=tag, offset=0x10)
    die.attributes = attributes or {}
    die.iter_children.return_value = []
    return die


def _attr(value: object) -> Mock:
    return Mock(value=value)


@pytest.mark.unit
def test_template_type_parameter_supports_default_and_missing_name() -> None:
    parser = _parser()
    parser.type_resolver.resolve_type_name.return_value = "u32"

    parameter = _die(
        "DW_TAG_template_type_param",
        {"DW_AT_name": _attr(b"T"), "DW_AT_type": _attr(0x22)},
    )
    result = parser.parse_template_type_param(parameter)

    assert result is not None
    assert result.name == "T"
    assert result.default_type == "u32"
    assert parser.parse_template_type_param(_die("DW_TAG_template_type_param")) is None


@pytest.mark.unit
def test_template_value_parameter_defaults_unknown_type_and_reads_constant() -> None:
    parser = _parser()
    parser.type_resolver.resolve_type_name.side_effect = ["unknown_type", "size_t"]

    parameter = _die(
        "DW_TAG_template_value_param",
        {"DW_AT_name": _attr("Count"), "DW_AT_type": _attr(0x22), "DW_AT_const_value": _attr(4)},
    )
    result = parser.parse_template_value_param(parameter)

    assert result is not None
    assert result.name == "Count"
    assert result.type_name == "int"
    assert result.default_value == 4
    assert parser.parse_template_value_param(_die("DW_TAG_template_value_param")) is None


@pytest.mark.unit
def test_inheritance_hierarchy_is_reversed_and_stops_on_cycles_or_missing_classes() -> None:
    parser = _parser()
    base = _die("DW_TAG_inheritance")
    base.attributes = {}
    parser.type_resolver.resolve_type_name.side_effect = ["Base", "Root"]
    derived = _die("DW_TAG_class_type")
    derived.iter_children.return_value = [base]
    parent = _die("DW_TAG_class_type")
    parent.iter_children.return_value = [base]
    parser.find_class = Mock(side_effect=[(Mock(), derived), (Mock(), parent), None])

    assert parser.build_inheritance_hierarchy("Derived") == ["Root", "Base"]

    parser.type_resolver.resolve_type_name.side_effect = None
    parser.type_resolver.resolve_type_name.return_value = "Derived"
    parser.find_class = Mock(return_value=(Mock(), derived))
    assert parser.build_inheritance_hierarchy("Derived") == ["Derived"]


@pytest.mark.unit
def test_inheritance_hierarchy_ignores_unknown_base() -> None:
    parser = _parser()
    inheritance = _die("DW_TAG_inheritance")
    current = _die("DW_TAG_class_type")
    current.iter_children.return_value = [inheritance]
    parser.find_class = Mock(return_value=(Mock(), current))
    parser.type_resolver.resolve_type_name.return_value = "unknown_type"

    assert parser.build_inheritance_hierarchy("Current") == []

"""Tests for special-case header rendering."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.generation.special_header_renderer import (
    SpecialHeaderRenderer,
)


@pytest.mark.unit
def test_not_found_header_is_deterministic() -> None:
    header = SpecialHeaderRenderer.render_not_found("MissingType")

    assert header.startswith("#ifndef MISSINGTYPE_H\n#define MISSINGTYPE_H")
    assert "Class 'MissingType' not found" in header
    assert header.endswith("#endif // MISSINGTYPE_H\n")


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

    assert "#ifndef GAME_LAYOUT_NAMESPACE_H" in header
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

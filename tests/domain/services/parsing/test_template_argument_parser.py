"""Unit tests for the canonical bounded delimiter-aware template argument splitter."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing.template_argument_parser import (
    split_template_arguments,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_split_empty_arguments() -> None:
    assert split_template_arguments("") == []
    assert split_template_arguments("   ") == []


def test_split_simple_arguments() -> None:
    assert split_template_arguments("int, float, char*") == ["int", "float", "char*"]


def test_split_nested_templates() -> None:
    expr = "std::map<int, std::vector<float>>, double"
    assert split_template_arguments(expr) == ["std::map<int, std::vector<float>>", "double"]


def test_split_member_function_pointer_arguments() -> None:
    expr = "void (MtObject::*)(unsigned int, unsigned int, float, float, float, unsigned int)"
    assert split_template_arguments(expr) == [expr]


def test_split_mixed_member_function_pointers() -> None:
    expr = "int, void (MtObject::*)(int, int), double, bool (MtObject::*)()"
    assert split_template_arguments(expr) == [
        "int",
        "void (MtObject::*)(int, int)",
        "double",
        "bool (MtObject::*)()",
    ]


def test_split_array_and_brace_delimiters() -> None:
    expr = "int[4][2], Struct<{1, 2}>, float"
    assert split_template_arguments(expr) == ["int[4][2]", "Struct<{1, 2}>", "float"]

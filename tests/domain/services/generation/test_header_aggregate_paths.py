"""Aggregate rendering and include-planning branch coverage."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MemberInfo,
    StructInfo,
    UnionInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderGenerator


@pytest.mark.unit
def test_header_renders_enum_struct_union_and_bitfield_members() -> None:
    generator = HeaderGenerator(Mock())
    info = ClassInfo(
        name="Aggregates",
        byte_size=32,
        members=[],
        methods=[],
        base_classes=[],
        enums=[EnumInfo("Mode", 4, [EnumeratorInfo("MODE_A", 0), EnumeratorInfo("MODE_B", 1)])],
        nested_structs=[StructInfo("Payload", 8, [MemberInfo("value", "u32", offset=0)], 0x12)],
        unions=[
            UnionInfo(
                "Choice",
                8,
                [MemberInfo("number", "u32", offset=0)],
                [StructInfo(None, 4, [MemberInfo("flag", "bool", offset=0)], 0x13)],
                0x14,
            )
        ],
        die_offset=0x10,
    )

    header = generator.generate_header(info, include_metadata=False)

    assert "enum class Mode" in header
    assert "struct Payload" in header
    assert "union Choice" in header
    assert "number;" in header
    assert "flag;" in header


@pytest.mark.unit
def test_single_class_header_plans_dependency_and_base_includes() -> None:
    generator = HeaderGenerator(Mock())
    info = ClassInfo(
        name="Derived",
        byte_size=8,
        members=[],
        methods=[],
        base_classes=["Base"],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=0x20,
    )

    header = generator.generate_single_class_header(
        info,
        class_dependencies={"Derived": "Derived.h", "Base": "Base.h", "Value": "Value.hpp"},
        typedefs={"size_t": "long", "u32": "unsigned int"},
        include_metadata=True,
    )

    assert '#include "Base.h"' in header
    assert '#include "Value.hpp"' in header
    assert '#include "Derived.h"' not in header
    assert "typedef unsigned int u32;" in header
    assert "typedef long size_t;" not in header

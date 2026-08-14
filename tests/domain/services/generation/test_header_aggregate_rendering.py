"""Regression tests for inline aggregate header rendering."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    StructInfo,
    UnionInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer


@pytest.mark.unit
def test_inline_anonymous_aggregate_member_is_valid_cpp() -> None:
    generator = HeaderRenderer(Mock())
    class_info = ClassInfo(
        name="DataFormat",
        byte_size=4,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[
            UnionInfo(
                name="",
                byte_size=4,
                members=[
                    MemberInfo(
                        "m_bits",
                        "anonymous_struct",
                        inline_struct=StructInfo(
                            name=None,
                            byte_size=4,
                            members=[MemberInfo("flag", "uint32_t", bit_size=1)],
                        ),
                    )
                ],
                nested_structs=[],
            )
        ],
        die_offset=0x5800,
    )

    header = generator.generate_header(class_info, include_metadata=False)

    assert "struct {" in header
    assert "uint32_t flag : 1;" in header
    assert "class_type" not in header

#!/usr/bin/env python3

"""Comprehensive unit tests for packing analyzer module.

Tests struct packing analysis with memory layout calculations.
"""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo
from ddon_dwarf_reconstructor.domain.services.generation.packing_analyzer import (
    analyze_member_gaps,
    calculate_packing_info,
    estimate_member_size,
)


class TestPackingAnalyzer:
    """Test suite for struct packing analysis functionality."""

    @pytest.fixture
    def mock_class_info(self):
        """Create realistic mock ClassInfo based on MtObject structure."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "MtObject"
        class_info.byte_size = 24

        members = []

        # Base vtable pointer (8 bytes on x64)
        vtable_member = Mock(spec=MemberInfo)
        vtable_member.name = "__vtable"
        vtable_member.type_name = "void*"
        vtable_member.offset = 0
        members.append(vtable_member)

        # Integer field with padding
        int_member = Mock(spec=MemberInfo)
        int_member.name = "m_nId"
        int_member.type_name = "int"
        int_member.offset = 8
        members.append(int_member)

        # Char with natural padding
        char_member = Mock(spec=MemberInfo)
        char_member.name = "m_cState"
        char_member.type_name = "char"
        char_member.offset = 12
        members.append(char_member)

        # Double aligned to 8-byte boundary
        double_member = Mock(spec=MemberInfo)
        double_member.name = "m_dValue"
        double_member.type_name = "double"
        double_member.offset = 16
        members.append(double_member)

        class_info.members = members
        return class_info

    @pytest.mark.unit
    def test_calculate_packing_info_with_large_padding(self):
        """Test packing analysis with significant padding."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "PaddedStruct"
        class_info.byte_size = 32

        members = []

        # Small member with large gap after it
        member1 = Mock(spec=MemberInfo)
        member1.name = "small_field"
        member1.type_name = "char"
        member1.offset = 0
        members.append(member1)

        # Next member far away, creating large gap
        member2 = Mock(spec=MemberInfo)
        member2.name = "far_field"
        member2.type_name = "int"
        member2.offset = 16
        members.append(member2)

        class_info.members = members

        result = calculate_packing_info(class_info)

        # Should detect significant padding
        assert result["total_padding"] > 0
        assert result["suggested_packing"] >= 4

    @pytest.mark.unit
    def test_estimate_member_size_const_types(self):
        """Test size estimation with const qualifiers."""
        assert estimate_member_size("const int") == 4
        assert estimate_member_size("const char*") == 8
        assert estimate_member_size("const double") == 8

    @pytest.mark.unit
    def test_estimate_member_size_references(self):
        """Test size estimation for reference types."""
        assert estimate_member_size("int&") == 8
        assert estimate_member_size("char&") == 8
        assert estimate_member_size("double&") == 8

    @pytest.mark.unit
    def test_analyze_member_gaps_with_tail_padding(self):
        """Test gap analysis detecting tail padding."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "TailPaddedStruct"
        class_info.byte_size = 16  # Larger than needed for alignment

        members = []
        member = Mock(spec=MemberInfo)
        member.name = "small_field"
        member.type_name = "char"
        member.offset = 0
        members.append(member)

        class_info.members = members
        gaps = analyze_member_gaps(class_info)

        # Should detect tail padding
        tail_gap = next((gap for gap in gaps if gap["after_member"] == "small_field"), None)
        assert tail_gap is not None
        assert tail_gap["size"] > 0

    @pytest.mark.unit
    def test_calculate_packing_info_members_with_none_offset(self):
        """Test packing analysis with members having None offset."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "TestStruct"
        class_info.byte_size = 8

        members = []
        member = Mock(spec=MemberInfo)
        member.name = "field_no_offset"
        member.type_name = "int"
        member.offset = None  # No offset information
        members.append(member)

        class_info.members = members

        # Should handle None offsets gracefully
        result = calculate_packing_info(class_info)
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_estimate_member_size_invalid_array(self):
        """Test size estimation with malformed array syntax."""
        # Invalid array syntax should fall back to pointer size
        assert estimate_member_size("int[abc]") == 8
        assert estimate_member_size("char[]") == 8
        assert estimate_member_size("type[") == 8

    @pytest.mark.unit
    def test_analyze_member_gaps_overlapping_members(self):
        """Test gap analysis with overlapping members (union-like)."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "UnionLikeStruct"
        class_info.byte_size = 8

        members = []

        # Two members at same offset (union behavior)
        member1 = Mock(spec=MemberInfo)
        member1.name = "union_int"
        member1.type_name = "int"
        member1.offset = 0
        members.append(member1)

        member2 = Mock(spec=MemberInfo)
        member2.name = "union_float"
        member2.type_name = "float"
        member2.offset = 0  # Same offset
        members.append(member2)

        class_info.members = members

        # Should handle overlapping members gracefully
        gaps = analyze_member_gaps(class_info)
        assert isinstance(gaps, list)

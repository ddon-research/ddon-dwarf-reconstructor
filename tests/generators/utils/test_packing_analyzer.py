#!/usr/bin/env python3

"""Comprehensive unit tests for packing analyzer module.

Tests struct packing analysis with memory layout calculations.
"""

from unittest.mock import Mock

import pytest

from src.ddon_dwarf_reconstructor.generators.utils.packing_analyzer import (
    analyze_member_gaps,
    calculate_packing_info,
    estimate_member_size,
    suggest_pragma_pack,
)
from src.ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo


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
    def test_calculate_packing_info_basic(self, mock_class_info):
        """Test basic struct packing analysis."""
        result = calculate_packing_info(mock_class_info)

        assert isinstance(result, dict)
        assert "suggested_packing" in result
        assert "total_padding" in result
        assert "natural_size" in result
        assert "actual_size" in result
        assert result["actual_size"] == 24

    @pytest.mark.unit
    def test_calculate_packing_info_empty_class(self):
        """Test packing analysis with empty class."""
        empty_class = Mock(spec=ClassInfo)
        empty_class.name = "EmptyClass"
        empty_class.byte_size = 0
        empty_class.members = []

        result = calculate_packing_info(empty_class)

        assert result["suggested_packing"] == 1
        assert result["total_padding"] == 0
        assert result["actual_size"] == 0

    @pytest.mark.unit
    def test_estimate_member_size_primitives(self):
        """Test size estimation for primitive types."""
        # Test basic types
        assert estimate_member_size("char") == 1
        assert estimate_member_size("bool") == 1
        assert estimate_member_size("int") == 4
        assert estimate_member_size("float") == 4
        assert estimate_member_size("double") == 8
        assert estimate_member_size("long") == 8

    @pytest.mark.unit
    def test_estimate_member_size_pointers(self):
        """Test size estimation for pointer types."""
        assert estimate_member_size("void*") == 8
        assert estimate_member_size("char*") == 8
        assert estimate_member_size("int*") == 8
        assert estimate_member_size("MtObject*") == 8

    @pytest.mark.unit
    def test_estimate_member_size_arrays(self):
        """Test size estimation for array types."""
        assert estimate_member_size("char[10]") == 10
        assert estimate_member_size("int[5]") == 20  # 4 * 5
        assert estimate_member_size("double[3]") == 24  # 8 * 3

    @pytest.mark.unit
    def test_estimate_member_size_unknown_types(self):
        """Test size estimation for unknown/complex types."""
        # Unknown types default to pointer size
        assert estimate_member_size("CustomClass") == 8
        assert estimate_member_size("std::string") == 8
        assert estimate_member_size("ComplexType") == 8

    @pytest.mark.unit
    def test_analyze_member_gaps_with_padding(self, mock_class_info):
        """Test gap analysis with padding between members."""
        gaps = analyze_member_gaps(mock_class_info)

        assert isinstance(gaps, list)
        # Should detect some gaps due to alignment
        # Should return a list (may be empty if no gaps)

        # Check gap structure if any exist
        for gap in gaps:
            assert "after_member" in gap
            assert "offset" in gap
            assert "size" in gap
            assert isinstance(gap["size"], int)
            assert gap["size"] > 0

    @pytest.mark.unit
    def test_analyze_member_gaps_no_members(self):
        """Test gap analysis with class having no members."""
        empty_class = Mock(spec=ClassInfo)
        empty_class.name = "EmptyClass"
        empty_class.byte_size = 0
        empty_class.members = []

        gaps = analyze_member_gaps(empty_class)

        assert isinstance(gaps, list)
        assert len(gaps) == 0

    @pytest.mark.unit
    def test_analyze_member_gaps_tightly_packed(self):
        """Test gap analysis with tightly packed structure."""
        class_info = Mock(spec=ClassInfo)
        class_info.name = "PackedStruct"
        class_info.byte_size = 4

        members = []
        for i in range(4):
            member = Mock(spec=MemberInfo)
            member.name = f"byte_{i}"
            member.type_name = "char"
            member.offset = i
            members.append(member)

        class_info.members = members
        gaps = analyze_member_gaps(class_info)

        # Tightly packed should have no gaps
        assert len(gaps) == 0

    @pytest.mark.unit
    def test_suggest_pragma_pack_byte_aligned(self):
        """Test pragma pack suggestion for byte-aligned structs."""
        packing_info: dict[str, int | None] = {"suggested_packing": 1}

        pragma = suggest_pragma_pack(packing_info)

        assert pragma == "#pragma pack(push, 1)"

    @pytest.mark.unit
    def test_suggest_pragma_pack_four_byte_aligned(self):
        """Test pragma pack suggestion for 4-byte aligned structs."""
        packing_info: dict[str, int | None] = {"suggested_packing": 4}

        pragma = suggest_pragma_pack(packing_info)

        assert pragma == "#pragma pack(push, 4)"

    @pytest.mark.unit
    def test_suggest_pragma_pack_default_alignment(self):
        """Test pragma pack suggestion for default (8-byte) alignment."""
        packing_info: dict[str, int | None] = {"suggested_packing": 8}

        pragma = suggest_pragma_pack(packing_info)

        assert pragma is None  # No pragma needed for default alignment

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
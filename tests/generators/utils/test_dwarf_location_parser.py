#!/usr/bin/env python3

"""Unit tests for DWARF location expression parser.

Tests both PS4 (integer offsets) and PS3 (location expressions) formats
to ensure robust handling of member offset extraction across DWARF versions.
"""

import pytest

from src.ddon_dwarf_reconstructor.generators.utils.dwarf_location_parser import (
    parse_location_offset,
)


class TestParseLocationOffsetIntegerFormats:
    """Test integer offset parsing (PS4 DWARF3/4 format)."""

    @pytest.mark.unit
    def test_parse_simple_integer_offset(self) -> None:
        """Test parsing simple integer offset (most common PS4 case)."""
        assert parse_location_offset(0) == 0
        assert parse_location_offset(4) == 4
        assert parse_location_offset(8) == 8
        assert parse_location_offset(16) == 16
        assert parse_location_offset(32) == 32

    @pytest.mark.unit
    def test_parse_large_integer_offset(self) -> None:
        """Test parsing larger offset values."""
        assert parse_location_offset(256) == 256
        assert parse_location_offset(1024) == 1024
        assert parse_location_offset(4096) == 4096

    @pytest.mark.unit
    def test_parse_negative_integer_offset(self) -> None:
        """Test parsing negative offsets (less common but possible)."""
        assert parse_location_offset(-1) == -1
        assert parse_location_offset(-4) == -4


class TestParseLocationOffsetLocationExpressions:
    """Test location expression parsing (PS3 DWARF2 format)."""

    @pytest.mark.unit
    def test_parse_dw_op_plus_uconst_expression(self) -> None:
        """Test parsing DW_OP_plus_uconst location expressions.

        This is the most common format in PS3 DWARF2:
        [35, offset] where 35 = 0x23 = DW_OP_plus_uconst
        """
        # MtDTI members from PS3 EBOOT.ELF
        assert parse_location_offset([35, 0]) == 0  # _vptr$
        assert parse_location_offset([35, 4]) == 4  # mName
        assert parse_location_offset([35, 8]) == 8  # mpNext
        assert parse_location_offset([35, 12]) == 12  # mpChild
        assert parse_location_offset([35, 16]) == 16  # mpParent
        assert parse_location_offset([35, 20]) == 20  # mpLink
        assert parse_location_offset([35, 24]) == 24  # mSize
        assert parse_location_offset([35, 28]) == 28  # mID

    @pytest.mark.unit
    def test_parse_single_value_expression(self) -> None:
        """Test parsing single-value location expressions."""
        assert parse_location_offset([4]) == 4
        assert parse_location_offset([8]) == 8
        assert parse_location_offset([16]) == 16

    @pytest.mark.unit
    def test_parse_tuple_location_expression(self) -> None:
        """Test that tuples are also accepted (pyelftools sometimes returns tuples)."""
        assert parse_location_offset((35, 4)) == 4
        assert parse_location_offset((35, 8)) == 8
        assert parse_location_offset((4,)) == 4


class TestParseLocationOffsetEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_parse_none_value(self) -> None:
        """Test that None returns None."""
        assert parse_location_offset(None) is None

    @pytest.mark.unit
    def test_parse_empty_list(self) -> None:
        """Test that empty list returns None."""
        assert parse_location_offset([]) is None

    @pytest.mark.unit
    def test_parse_empty_tuple(self) -> None:
        """Test that empty tuple returns None."""
        assert parse_location_offset(()) is None

    @pytest.mark.unit
    def test_parse_unknown_opcode(self) -> None:
        """Test that unknown opcodes return None."""
        # Opcode 99 is not DW_OP_plus_uconst (35)
        assert parse_location_offset([99, 4]) is None

    @pytest.mark.unit
    def test_parse_malformed_expression_non_int_offset(self) -> None:
        """Test that malformed expressions (non-int offset) return None."""
        # DW_OP_plus_uconst with string offset instead of int
        assert parse_location_offset([35, "invalid"]) is None  # type: ignore

    @pytest.mark.unit
    def test_parse_unknown_type(self) -> None:
        """Test that unknown types return None."""
        assert parse_location_offset("invalid") is None  # type: ignore
        assert parse_location_offset({"invalid": "dict"}) is None  # type: ignore
        # [35] alone is a valid single-value expression
        assert parse_location_offset([35]) == 35


class TestParseLocationOffsetRealWorldData:
    """Test with actual data from PS3 and PS4 ELF files."""

    @pytest.mark.unit
    def test_mtdti_class_members_ps3(self) -> None:
        """Test MtDTI class members from PS3 EBOOT.ELF.

        Real data extracted from DWARF2 debug info.
        All members use [35, offset] format (DW_OP_plus_uconst).
        """
        members = [
            ([35, 0], 0),      # _vptr$
            ([35, 4], 4),      # mName
            ([35, 8], 8),      # mpNext
            ([35, 12], 12),    # mpChild
            ([35, 16], 16),    # mpParent
            ([35, 20], 20),    # mpLink
            ([35, 24], 24),    # mSize
            ([35, 28], 28),    # mID
        ]

        for expr, expected_offset in members:
            assert parse_location_offset(expr) == expected_offset

    @pytest.mark.unit
    def test_ps4_integer_offsets(self) -> None:
        """Test typical PS4 DWARF3/4 integer offsets."""
        # Simulated PS4 class members with direct integer offsets
        members = [
            (0, 0),
            (8, 8),
            (16, 16),
            (24, 24),
            (32, 32),
        ]

        for offset, expected in members:
            assert parse_location_offset(offset) == expected

    @pytest.mark.unit
    def test_mixed_formats_compatibility(self) -> None:
        """Test that code handles both PS3 and PS4 formats in same call."""
        # Simulate processing members from both PS3 and PS4 files
        results = [
            parse_location_offset(4),          # PS4 integer
            parse_location_offset([35, 4]),    # PS3 location expression
            parse_location_offset(8),          # PS4 integer
            parse_location_offset([35, 8]),    # PS3 location expression
        ]

        assert results == [4, 4, 8, 8]


class TestParseLocationOffsetIntegration:
    """Integration tests with various scenarios."""

    @pytest.mark.unit
    def test_class_member_extraction_workflow(self) -> None:
        """Simulate typical class member offset extraction workflow."""
        # Simulate extracting offsets from a class with multiple members

        # PS3 DWARF2 format
        ps3_members = {
            "_vptr$": [35, 0],
            "mName": [35, 4],
            "mpNext": [35, 8],
            "type_field": [35, 16],
        }

        ps3_offsets = {
            name: parse_location_offset(attr) for name, attr in ps3_members.items()
        }

        assert ps3_offsets == {
            "_vptr$": 0,
            "mName": 4,
            "mpNext": 8,
            "type_field": 16,
        }

        # PS4 DWARF3/4 format
        ps4_members = {
            "field1": 0,
            "field2": 8,
            "field3": 16,
            "field4": 24,
        }

        ps4_offsets = {
            name: parse_location_offset(attr) for name, attr in ps4_members.items()
        }

        assert ps4_offsets == {
            "field1": 0,
            "field2": 8,
            "field3": 16,
            "field4": 24,
        }

    @pytest.mark.unit
    def test_offset_extraction_with_filter(self) -> None:
        """Test extracting offsets and filtering out None values."""
        mixed_attributes = [
            4,              # Valid PS4
            [35, 8],        # Valid PS3
            None,           # Invalid - None
            [99, 12],       # Invalid - unknown opcode
            16,             # Valid PS4
            [],             # Invalid - empty
            [35, 20],       # Valid PS3
        ]

        offsets = [
            parse_location_offset(attr)
            for attr in mixed_attributes
            if parse_location_offset(attr) is not None
        ]

        assert offsets == [4, 8, 16, 20]

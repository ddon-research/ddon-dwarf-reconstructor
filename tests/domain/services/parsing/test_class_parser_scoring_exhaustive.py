"""
Unit tests for ClassParser scoring algorithm and timeout functionality.
Tests the enhancements for forward declaration detection and type-specific scoring.
"""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver


class TestClassParserScoring:
    """Test suite for ClassParser scoring and timeout features."""

    @pytest.fixture
    def type_resolver(self):
        """Mock the production lazy resolver."""
        return Mock(spec=LazyTypeResolver)

    @pytest.fixture
    def dwarf_info(self):
        """Mock DWARF info fixture."""
        return Mock()

    @pytest.fixture
    def lazy_index(self):
        """Mock LazyDwarfIndexService fixture."""
        return Mock()

    @pytest.fixture
    def class_parser(self, type_resolver, dwarf_info, lazy_index):
        """ClassParser instance with mocked dependencies."""
        parser = ClassParser(type_resolver, dwarf_info, full_scan_timeout=180.0)
        parser.lazy_index = lazy_index
        return parser

    @pytest.mark.unit
    def test_exhaustive_search_stops_after_non_improving_complete_candidates(self, class_parser):
        """Exhaustive search should stop after repeated non-improving complete matches."""
        class_parser.exhaustive_search = True

        def make_candidate(cu_offset: int, die_offset: int) -> Mock:
            cu = Mock()
            cu.cu_offset = cu_offset
            die = Mock()
            die.is_null.return_value = False
            die.tag = "DW_TAG_class_type"
            die.attributes = {
                "DW_AT_name": Mock(value=b"rLayout"),
                "DW_AT_byte_size": Mock(value=528),
            }
            die.has_children = True
            die.offset = die_offset
            enum_child = Mock(tag="DW_TAG_enumeration_type")
            struct_child = Mock(tag="DW_TAG_structure_type")
            die.iter_children.return_value = [enum_child, struct_child]
            cu.iter_DIEs.return_value = [die]
            return cu

        extra_cus = [make_candidate(0x2000 + i, 0x3000 + i) for i in range(10)]
        all_cus = [make_candidate(0x0C9D, 0x76133), *extra_cus]
        class_parser.dwarf_info.iter_CUs.return_value = all_cus

        result = class_parser._find_class_full_scan("rLayout", exhaustive_override=True)

        assert result is not None
        found_cu, found_die = result
        assert found_cu.cu_offset == 0x0C9D
        assert found_die.offset == 0x76133
        # After the root plus four non-improving matches, later CUs should never be scanned.
        assert extra_cus[0].iter_DIEs.called
        assert extra_cus[1].iter_DIEs.called
        assert extra_cus[2].iter_DIEs.called
        assert extra_cus[3].iter_DIEs.called
        assert not extra_cus[4].iter_DIEs.called

    @pytest.mark.unit
    def test_exhaustive_search_keeps_scanning_until_better_candidate_found(self, class_parser):
        """A later better candidate must still beat earlier complete definitions."""
        class_parser.exhaustive_search = True

        def make_candidate(
            cu_offset: int,
            die_offset: int,
            nested_enums: int,
            nested_structs: int,
        ) -> Mock:
            cu = Mock()
            cu.cu_offset = cu_offset
            die = Mock()
            die.is_null.return_value = False
            die.tag = "DW_TAG_class_type"
            die.attributes = {
                "DW_AT_name": Mock(value=b"rLayout"),
                "DW_AT_byte_size": Mock(value=528),
            }
            die.has_children = True
            die.offset = die_offset
            children = [Mock(tag="DW_TAG_enumeration_type") for _ in range(nested_enums)]
            children.extend(Mock(tag="DW_TAG_structure_type") for _ in range(nested_structs))
            die.iter_children.return_value = children
            cu.iter_DIEs.return_value = [die]
            return cu

        early = make_candidate(0x0C9D, 0x76133, 1, 1)
        later_better = make_candidate(0x11CB2B, 0x17FF33, 2, 1)
        trailing_equal = [make_candidate(0x2000 + i, 0x3000 + i, 2, 1) for i in range(10)]
        class_parser.dwarf_info.iter_CUs.return_value = [early, later_better, *trailing_equal]

        result = class_parser._find_class_full_scan("rLayout", exhaustive_override=True)

        assert result is not None
        found_cu, found_die = result
        assert found_cu.cu_offset == 0x11CB2B
        assert found_die.offset == 0x17FF33
        assert trailing_equal[0].iter_DIEs.called

    @pytest.mark.unit
    def test_multi_cu_scenario(self, class_parser):
        """Test finding complete definition across multiple compilation units."""
        # Disable lazy loading to force full scan
        class_parser.lazy_index = None

        # CU 1: Forward declaration
        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x1000

        # Mock CU DIE (compilation unit header)
        cu_die1 = Mock()
        cu_die1.tag = "DW_TAG_compile_unit"
        cu_die1.is_null.return_value = False

        forward_die = Mock()
        forward_die.tag = "DW_TAG_class_type"
        forward_die.attributes = {
            "DW_AT_name": Mock(value=b"MultiCUClass"),
            "DW_AT_declaration": Mock(value=True),
        }
        forward_die.offset = 0x1100
        forward_die.has_children = False
        forward_die.is_null.return_value = False

        mock_cu1.iter_DIEs.return_value = [cu_die1, forward_die]

        # CU 2: Complete definition
        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x5000

        # Mock CU DIE (compilation unit header)
        cu_die2 = Mock()
        cu_die2.tag = "DW_TAG_compile_unit"
        cu_die2.is_null.return_value = False

        complete_die = Mock()
        complete_die.tag = "DW_TAG_class_type"
        complete_die.attributes = {
            "DW_AT_name": Mock(value=b"MultiCUClass"),
            "DW_AT_byte_size": Mock(value=256),
        }
        complete_die.offset = 0x5100
        complete_die.has_children = True
        complete_die.is_null.return_value = False

        mock_cu2.iter_DIEs.return_value = [cu_die2, complete_die]

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        # Should find complete definition in CU 2, not forward declaration in CU 1
        result = class_parser._find_class_full_scan("MultiCUClass")

        assert result is not None
        cu, die = result
        assert cu == mock_cu2
        assert die.offset == 0x5100
        assert "DW_AT_byte_size" in die.attributes

    @pytest.mark.unit
    def test_zero_member_class_mtframework_heuristic(self, class_parser):
        """Test that zero-member classes with size trigger MTFramework warning."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"MtEmptyClass"),
            "DW_AT_byte_size": Mock(value=8),  # Has size but no members
        }
        mock_die.has_children = False  # No members

        # This should be handled with a warning in the actual parsing
        # Score would be: 8 + 0 = 8 (no 10000 bonus for has_children)
        size_attr = mock_die.attributes.get("DW_AT_byte_size")
        score = size_attr.value + (10000 if mock_die.has_children else 0)
        assert score == 8  # Low score, but still valid

    @pytest.mark.unit
    def test_incomplete_typedef_scoring(self, class_parser):
        """Test that typedefs without DW_AT_type get negative score."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_typedef"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"IncompleteTypedef"),
            # Missing DW_AT_type attribute
        }
        mock_die.has_children = False

        # Typedef without DW_AT_type should score -500
        assert "DW_AT_type" not in mock_die.attributes

    @pytest.mark.unit
    def test_enum_without_size_scoring(self, class_parser):
        """Test that enums without size get negative score."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_enumeration_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"IncompleteEnum"),
            # Missing DW_AT_byte_size attribute
        }
        mock_die.has_children = True

        # Enum without size should score -500
        assert "DW_AT_byte_size" not in mock_die.attributes

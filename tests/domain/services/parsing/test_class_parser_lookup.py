"""
Comprehensive unit tests for ClassParser module.
Tests the core DWARF class parsing functionality with proper mocks.
"""

from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver


class TestClassParser:
    """Test suite for ClassParser functionality."""

    @pytest.fixture
    def type_resolver(self):
        """Mock the production lazy resolver."""
        return Mock(spec=LazyTypeResolver)

    @pytest.fixture
    def dwarf_info(self):
        """Mock DWARF info fixture."""
        return Mock()

    @pytest.fixture
    def class_parser(self, type_resolver, dwarf_info):
        """ClassParser instance with mocked dependencies."""
        return ClassParser(type_resolver, dwarf_info)

    @pytest.mark.unit
    def test_find_class_success(self, class_parser):
        """Test finding a class in DWARF info."""
        # Mock DIE
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=16),
        }
        mock_die.offset = 0x2000  # Add real offset for logging
        mock_die.is_null.return_value = False
        mock_die.has_children = True

        # Mock compilation unit
        mock_cu = Mock()
        mock_cu.iter_DIEs.return_value = [mock_die]
        mock_cu.cu_offset = 0x1000  # Add cu_offset for logging

        # Mock dwarf_info
        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu]

        result = class_parser.find_class("TestClass")

        assert result is not None
        assert result[0] == mock_cu
        assert result[1] == mock_die

    @pytest.mark.unit
    def test_find_class_not_found(self, class_parser):
        """Test finding a class that doesn't exist."""
        # Mock DIE with different name
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"OtherClass")}

        # Mock compilation unit
        mock_cu = Mock()
        mock_cu.iter_DIEs.return_value = [mock_die]
        mock_cu.cu_offset = 0x1000  # Add cu_offset for logging

        # Mock dwarf_info
        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu]

        result = class_parser.find_class("NonExistentClass")

        assert result is None

    @pytest.mark.unit
    def test_build_inheritance_hierarchy_simple(self, class_parser):
        """Test building inheritance hierarchy for a simple case."""
        # This is a complex method that would require extensive mocking
        # For now, test that it exists and can be called
        with patch.object(class_parser, "find_class") as mock_find:
            mock_find.return_value = None  # Class not found case

            result = class_parser.build_inheritance_hierarchy("NonExistentClass")

            assert result == []

    @pytest.mark.unit
    def test_find_class_forward_declaration_vs_complete(self, class_parser):
        """Test that complete definitions are preferred over forward declarations.

        Scenario: CU1 contains forward declaration, CU2 contains complete definition.
        Expected: Complete definition from CU2 is returned.
        """
        # Mock forward declaration in CU1
        mock_forward_die = Mock()
        mock_forward_die.tag = "DW_TAG_class_type"
        mock_forward_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_declaration": Mock(value=True),  # Forward declaration marker
        }
        mock_forward_die.offset = 0x1000
        mock_forward_die.has_children = False
        mock_forward_die.is_null.return_value = False

        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x100
        mock_cu1.iter_DIEs.return_value = [mock_forward_die]

        # Mock complete definition in CU2
        mock_complete_die = Mock()
        mock_complete_die.tag = "DW_TAG_class_type"
        mock_complete_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=128),
        }
        mock_complete_die.offset = 0x2000
        mock_complete_die.has_children = True
        mock_complete_die.is_null.return_value = False

        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x200
        mock_cu2.iter_DIEs.return_value = [mock_complete_die]

        # Mock dwarf_info to return both CUs
        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        result = class_parser.find_class("TestClass")

        # Should return CU2 and complete DIE, not forward declaration
        assert result is not None
        cu, die = result
        assert cu == mock_cu2
        assert die == mock_complete_die
        assert die.offset == 0x2000

    @pytest.mark.unit
    def test_find_class_declaration_attribute_detection(self, class_parser):
        """Test that DW_AT_declaration attribute is correctly detected."""
        # Mock DIE with declaration attribute
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"ForwardClass"),
            "DW_AT_declaration": Mock(value=True),
        }
        mock_die.offset = 0x1000
        mock_die.has_children = False
        mock_die.is_null.return_value = False

        mock_cu = Mock()
        mock_cu.cu_offset = 0x100
        mock_cu.iter_DIEs.return_value = [mock_die]

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu]

        result = class_parser.find_class("ForwardClass")

        # Should return the declaration as fallback (with warning logged)
        assert result is not None
        _, die = result
        assert die.attributes.get("DW_AT_declaration") is not None

    @pytest.mark.unit
    def test_find_class_scoring_has_children_and_size(self, class_parser):
        """Test scoring algorithm: has_children + byte_size > byte_size only."""
        # Mock candidate 1: Has size but no children (skeleton)
        mock_skeleton_die = Mock()
        mock_skeleton_die.tag = "DW_TAG_class_type"
        mock_skeleton_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=64),
        }
        mock_skeleton_die.offset = 0x1000
        mock_skeleton_die.has_children = False
        mock_skeleton_die.is_null.return_value = False

        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x100
        mock_cu1.iter_DIEs.return_value = [mock_skeleton_die]

        # Mock candidate 2: Has size AND children (complete)
        mock_complete_die = Mock()
        mock_complete_die.tag = "DW_TAG_class_type"
        mock_complete_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=64),
        }
        mock_complete_die.offset = 0x2000
        mock_complete_die.has_children = True
        mock_complete_die.is_null.return_value = False

        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x200
        mock_cu2.iter_DIEs.return_value = [mock_complete_die]

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        result = class_parser.find_class("TestClass")

        # Should prefer candidate with children (score: 10064) over skeleton (score: 64)
        assert result is not None
        cu, die = result
        assert cu == mock_cu2
        assert die.has_children is True
        assert die.offset == 0x2000

    @pytest.mark.unit
    def test_find_class_early_exit_perfect_match(self, class_parser):
        """Test early exit optimization when perfect match found.

        Perfect match: has_children=True, byte_size>0, no DW_AT_declaration.
        Should return immediately without scanning remaining CUs.
        """
        # Mock perfect match in CU1
        mock_perfect_die = Mock()
        mock_perfect_die.tag = "DW_TAG_class_type"
        mock_perfect_die.attributes = {
            "DW_AT_name": Mock(value=b"MtObject"),
            "DW_AT_byte_size": Mock(value=8),
        }
        mock_perfect_die.offset = 0x1000
        mock_perfect_die.has_children = True  # Has vtable or members
        mock_perfect_die.is_null.return_value = False

        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x100
        mock_cu1.iter_DIEs.return_value = [mock_perfect_die]

        # Mock another CU that shouldn't be checked
        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x200
        # This should never be called due to early exit
        mock_cu2.iter_DIEs.side_effect = AssertionError("CU2 should not be scanned")

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        result = class_parser.find_class("MtObject")

        # Should return perfect match from CU1 without scanning CU2
        assert result is not None
        cu, die = result
        assert cu == mock_cu1
        assert die == mock_perfect_die
        # Verify CU2 was never iterated (early exit worked)
        mock_cu2.iter_DIEs.assert_not_called()

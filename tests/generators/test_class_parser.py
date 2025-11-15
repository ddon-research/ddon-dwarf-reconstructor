"""
Comprehensive unit tests for ClassParser module.
Tests the core DWARF class parsing functionality with proper mocks.
"""

from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, TypeResolver


class TestClassParser:
    """Test suite for ClassParser functionality."""

    @pytest.fixture
    def type_resolver(self):
        """Mock TypeResolver fixture."""
        return Mock(spec=TypeResolver)

    @pytest.fixture
    def dwarf_info(self):
        """Mock DWARF info fixture."""
        return Mock()

    @pytest.fixture
    def class_parser(self, type_resolver, dwarf_info):
        """ClassParser instance with mocked dependencies."""
        return ClassParser(type_resolver, dwarf_info)

    @pytest.mark.unit
    def test_parse_class_info_basic_structure(self, class_parser):
        """Test basic class parsing with simple structure."""
        # Mock class DIE
        mock_class_die = Mock()
        mock_class_die.tag = "DW_TAG_class_type"
        mock_class_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=24),
        }
        mock_class_die.offset = 0x1000

        # Mock member DIE
        mock_member_die = Mock()
        mock_member_die.tag = "DW_TAG_member"
        mock_member_die.attributes = {
            "DW_AT_name": Mock(value=b"m_value"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x2000),
        }

        # Mock type DIE for member (terminal base type)
        mock_type_die = Mock()
        mock_type_die.tag = "DW_TAG_base_type"
        mock_type_die.offset = 0x2000  # Add offset for TypeChainTraverser
        mock_type_die.attributes = {"DW_AT_name": Mock(value=b"int")}

        mock_class_die.iter_children.return_value = [mock_member_die]
        mock_member_die.get_DIE_from_attribute.return_value = mock_type_die

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        result = class_parser.parse_class_info(Mock(), mock_class_die)

        assert result.name == "TestClass"
        assert result.byte_size == 24
        assert len(result.members) == 1
        assert result.members[0].name == "m_value"
        assert result.members[0].type_name == "int"
        assert result.members[0].type_offset == 0x2000  # Verify offset captured

    @pytest.mark.unit
    def test_parse_class_info_with_inheritance(self, class_parser):
        """Test class parsing with inheritance information."""
        # Mock class DIE with inheritance
        mock_class_die = Mock()
        mock_class_die.tag = "DW_TAG_class_type"
        mock_class_die.attributes = {
            "DW_AT_name": Mock(value=b"DerivedClass"),
            "DW_AT_byte_size": Mock(value=32),
        }
        mock_class_die.offset = 0x1000

        # Mock inheritance DIE
        mock_inheritance_die = Mock()
        mock_inheritance_die.tag = "DW_TAG_inheritance"
        mock_inheritance_die.attributes = {
            "DW_AT_type": Mock(value=0x5678),
            "DW_AT_data_member_location": Mock(value=0),
        }

        # Mock base class DIE
        mock_base_die = Mock()
        mock_base_die.tag = "DW_TAG_class_type"
        mock_base_die.attributes = {"DW_AT_name": Mock(value=b"BaseClass")}

        mock_class_die.iter_children.return_value = [mock_inheritance_die]
        mock_inheritance_die.get_DIE_from_attribute.return_value = mock_base_die

        # Mock type resolver to return base class name
        class_parser.type_resolver.resolve_type_name.return_value = "BaseClass"

        result = class_parser.parse_class_info(Mock(), mock_class_die)

        assert result.name == "DerivedClass"
        assert len(result.base_classes) == 1
        assert result.base_classes[0] == "BaseClass"

    @pytest.mark.unit
    def test_parse_member_with_basic_info(self, class_parser):
        """Test member parsing with basic information."""
        # Mock int member
        mock_member = Mock()
        mock_member.tag = "DW_TAG_member"
        mock_member.attributes = {
            "DW_AT_name": Mock(value=b"m_int"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x1111),
        }

        # Mock type DIE (terminal base type)
        mock_type = Mock()
        mock_type.tag = "DW_TAG_base_type"
        mock_type.offset = 0x1111  # Add offset for TypeChainTraverser
        mock_type.attributes = {"DW_AT_name": Mock(value=b"int")}
        mock_member.get_DIE_from_attribute.return_value = mock_type

        class_parser.type_resolver.resolve_type_name.return_value = "int"

        member = class_parser.parse_member(mock_member)

        assert member is not None
        assert member.name == "m_int"
        assert member.type_name == "int"
        assert member.offset == 0
        assert member.type_offset == 0x1111  # Verify offset captured

    @pytest.mark.unit
    def test_parse_member_with_bitfields(self, class_parser):
        """Test member parsing with bitfield information."""
        # Mock bitfield member
        mock_bitfield = Mock()
        mock_bitfield.tag = "DW_TAG_member"
        mock_bitfield.attributes = {
            "DW_AT_name": Mock(value=b"m_flag"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x3333),
            "DW_AT_bit_size": Mock(value=1),
            "DW_AT_bit_offset": Mock(value=7),
        }

        mock_type = Mock()
        mock_type.tag = "DW_TAG_base_type"
        mock_type.offset = 0x3333  # Add offset for TypeChainTraverser
        mock_type.attributes = {"DW_AT_name": Mock(value=b"unsigned char")}
        mock_bitfield.get_DIE_from_attribute.return_value = mock_type

        class_parser.type_resolver.resolve_type_name.return_value = "unsigned char"
        member = class_parser.parse_member(mock_bitfield)

        assert member is not None
        assert member.name == "m_flag"
        assert member.type_name == "unsigned char"
        assert member.type_offset == 0x3333  # Verify offset captured
        # Note: bit_size and bit_offset not stored in MemberInfo model

    @pytest.mark.unit
    def test_parse_method_basic_function(self, class_parser):
        """Test method parsing for basic member functions."""
        # Mock method DIE
        mock_method = Mock()
        mock_method.tag = "DW_TAG_subprogram"
        mock_method.attributes = {
            "DW_AT_name": Mock(value=b"getValue"),
            "DW_AT_type": Mock(value=0x4444),
        }

        # Mock return type (terminal base type)
        mock_return_type = Mock()
        mock_return_type.tag = "DW_TAG_base_type"
        mock_return_type.offset = 0x4444  # Add offset for TypeChainTraverser
        mock_return_type.attributes = {"DW_AT_name": Mock(value=b"int")}

        mock_method.get_DIE_from_attribute.return_value = mock_return_type
        mock_method.iter_children.return_value = []  # No parameters
        mock_method.get_parent.return_value = None  # No parent DIE

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        method = class_parser.parse_method(mock_method)

        assert method is not None
        assert method.name == "getValue"
        assert method.return_type == "int"
        assert method.return_type_offset == 0x4444  # Verify offset captured
        assert len(method.parameters) == 0

    @pytest.mark.unit
    def test_parse_parameter_basic(self, class_parser):
        """Test parameter parsing."""
        # Mock parameter DIE
        mock_param = Mock()
        mock_param.tag = "DW_TAG_formal_parameter"
        mock_param.attributes = {
            "DW_AT_name": Mock(value=b"value"),
            "DW_AT_type": Mock(value=0x5555),
        }

        # Mock type (terminal base type)
        mock_param_type = Mock()
        mock_param_type.tag = "DW_TAG_base_type"
        mock_param_type.offset = 0x5555  # Add offset for TypeChainTraverser
        mock_param_type.attributes = {"DW_AT_name": Mock(value=b"int")}
        mock_param.get_DIE_from_attribute.return_value = mock_param_type

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        param = class_parser.parse_parameter(mock_param)

        assert param is not None
        assert param.name == "value"
        assert param.type_name == "int"
        assert param.type_offset == 0x5555  # Verify offset captured

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
    def test_parse_class_info_missing_name(self, class_parser):
        """Test class parsing when name attribute is missing."""
        mock_class_die = Mock()
        mock_class_die.tag = "DW_TAG_class_type"
        mock_class_die.attributes = {"DW_AT_byte_size": Mock(value=16)}
        mock_class_die.offset = 0x1000
        mock_class_die.iter_children.return_value = []

        result = class_parser.parse_class_info(Mock(), mock_class_die)

        # Should handle gracefully with a default name
        assert result.name == "unknown_class"

    @pytest.mark.unit
    def test_parse_class_info_missing_byte_size(self, class_parser):
        """Test class parsing when byte_size attribute is missing."""
        mock_class_die = Mock()
        mock_class_die.tag = "DW_TAG_class_type"
        mock_class_die.attributes = {"DW_AT_name": Mock(value=b"TestClass")}
        mock_class_die.offset = 0x1000
        mock_class_die.iter_children.return_value = []

        result = class_parser.parse_class_info(Mock(), mock_class_die)

        assert result.name == "TestClass"
        assert result.byte_size == 0  # Default size when missing

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

    @pytest.mark.unit
    def test_find_class_lazy_cache_validation(self, class_parser):
        """Test that lazy loading validates cached entries are not forward declarations."""
        # Setup lazy index mock
        mock_lazy_index = Mock()
        class_parser.lazy_index = mock_lazy_index

        # Mock cache returns an offset
        mock_lazy_index.find_symbol_offset.return_value = 0x1000

        # Mock DIE at cached offset - forward declaration
        mock_forward_die = Mock()
        mock_forward_die.tag = "DW_TAG_class_type"
        mock_forward_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_declaration": Mock(value=True),  # Forward declaration!
        }
        mock_forward_die.offset = 0x1000
        mock_forward_die.has_children = False

        mock_cu = Mock()
        mock_cu.cu_offset = 0x100
        mock_cu.__getitem__ = Mock(return_value=0x500)  # Mock unit_length

        # Mock finding the DIE - should return the forward declaration
        with patch.object(class_parser, "_find_die_and_cu_by_offset") as mock_find:
            mock_find.return_value = (mock_cu, mock_forward_die)
            
            # Mock dwarf_info to return empty for full scan fallback
            class_parser.dwarf_info.iter_CUs.return_value = []

            result = class_parser.find_class("TestClass")

            # Should reject cached forward declaration and return None (no full scan match)
            assert result is None

    @pytest.mark.unit
    def test_find_class_scoring_declaration_penalty(self, class_parser):
        """Test that forward declarations receive heavy penalty in scoring."""
        # Mock forward declaration with size (shouldn't happen but test scoring)
        mock_forward_die = Mock()
        mock_forward_die.tag = "DW_TAG_class_type"
        mock_forward_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=100),
            "DW_AT_declaration": Mock(value=True),  # Declaration penalty: -1000
        }
        mock_forward_die.offset = 0x1000
        mock_forward_die.has_children = False
        mock_forward_die.is_null.return_value = False

        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x100
        mock_cu1.iter_DIEs.return_value = [mock_forward_die]

        # Mock complete definition with smaller size
        mock_complete_die = Mock()
        mock_complete_die.tag = "DW_TAG_class_type"
        mock_complete_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=8),  # Much smaller
        }
        mock_complete_die.offset = 0x2000
        mock_complete_die.has_children = True  # Score: 10008
        mock_complete_die.is_null.return_value = False

        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x200
        mock_cu2.iter_DIEs.return_value = [mock_complete_die]

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        result = class_parser.find_class("TestClass")

        # Should prefer small complete definition (score: 10008) over
        # large forward declaration (score: -1000+100=-900)
        assert result is not None
        cu, die = result
        assert cu == mock_cu2
        assert die.offset == 0x2000


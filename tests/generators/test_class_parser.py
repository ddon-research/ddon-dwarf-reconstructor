"""
Comprehensive unit tests for ClassParser module.
Tests the core DWARF class parsing functionality with proper mocks.
"""

import pytest
from unittest.mock import Mock, patch

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, TypeResolver
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo, MethodInfo, ParameterInfo


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
            "DW_AT_byte_size": Mock(value=24)
        }
        mock_class_die.offset = 0x1000

        # Mock member DIE
        mock_member_die = Mock()
        mock_member_die.tag = "DW_TAG_member"
        mock_member_die.attributes = {
            "DW_AT_name": Mock(value=b"m_value"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x2000)
        }

        # Mock type DIE for member
        mock_type_die = Mock()
        mock_type_die.tag = "DW_TAG_base_type"

        mock_class_die.iter_children.return_value = [mock_member_die]
        mock_member_die.get_DIE_from_attribute.return_value = mock_type_die

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        result = class_parser.parse_class_info(Mock(), mock_class_die)

        assert result.name == "TestClass"
        assert result.byte_size == 24
        assert len(result.members) == 1
        assert result.members[0].name == "m_value"
        assert result.members[0].type_name == "int"

    @pytest.mark.unit
    def test_parse_class_info_with_inheritance(self, class_parser):
        """Test class parsing with inheritance information."""
        # Mock class DIE with inheritance
        mock_class_die = Mock()
        mock_class_die.tag = "DW_TAG_class_type"
        mock_class_die.attributes = {
            "DW_AT_name": Mock(value=b"DerivedClass"),
            "DW_AT_byte_size": Mock(value=32)
        }
        mock_class_die.offset = 0x1000

        # Mock inheritance DIE
        mock_inheritance_die = Mock()
        mock_inheritance_die.tag = "DW_TAG_inheritance"
        mock_inheritance_die.attributes = {
            "DW_AT_type": Mock(value=0x5678),
            "DW_AT_data_member_location": Mock(value=0)
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
            "DW_AT_type": Mock(value=0x1111)
        }

        # Mock type DIE
        mock_type = Mock()
        mock_type.tag = "DW_TAG_base_type"
        mock_member.get_DIE_from_attribute.return_value = mock_type

        class_parser.type_resolver.resolve_type_name.return_value = "int"

        member = class_parser.parse_member(mock_member)

        assert member is not None
        assert member.name == "m_int"
        assert member.type_name == "int"
        assert member.offset == 0

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
            "DW_AT_bit_offset": Mock(value=7)
        }

        mock_type = Mock()
        mock_type.tag = "DW_TAG_base_type"
        mock_bitfield.get_DIE_from_attribute.return_value = mock_type

        class_parser.type_resolver.resolve_type_name.return_value = "unsigned char"
        member = class_parser.parse_member(mock_bitfield)

        assert member is not None
        assert member.name == "m_flag"
        assert member.type_name == "unsigned char"
        # Note: bit_size and bit_offset not stored in MemberInfo model

    @pytest.mark.unit
    def test_parse_method_basic_function(self, class_parser):
        """Test method parsing for basic member functions."""
        # Mock method DIE
        mock_method = Mock()
        mock_method.tag = "DW_TAG_subprogram"
        mock_method.attributes = {
            "DW_AT_name": Mock(value=b"getValue"),
            "DW_AT_type": Mock(value=0x4444)
        }

        # Mock return type
        mock_return_type = Mock()
        mock_return_type.tag = "DW_TAG_base_type"

        mock_method.get_DIE_from_attribute.return_value = mock_return_type
        mock_method.iter_children.return_value = []  # No parameters
        mock_method.get_parent.return_value = None  # No parent DIE

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        method = class_parser.parse_method(mock_method)

        assert method is not None
        assert method.name == "getValue"
        assert method.return_type == "int"
        assert len(method.parameters) == 0

    @pytest.mark.unit
    def test_parse_parameter_basic(self, class_parser):
        """Test parameter parsing."""
        # Mock parameter DIE
        mock_param = Mock()
        mock_param.tag = "DW_TAG_formal_parameter"
        mock_param.attributes = {
            "DW_AT_name": Mock(value=b"value"),
            "DW_AT_type": Mock(value=0x5555)
        }

        # Mock type
        mock_param_type = Mock()
        mock_param_type.tag = "DW_TAG_base_type"
        mock_param.get_DIE_from_attribute.return_value = mock_param_type

        class_parser.type_resolver.resolve_type_name.return_value = "int"
        param = class_parser.parse_parameter(mock_param)

        assert param is not None
        assert param.name == "value"
        assert param.type_name == "int"

    @pytest.mark.unit
    def test_find_class_success(self, class_parser):
        """Test finding a class in DWARF info."""
        # Mock DIE
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {'DW_AT_name': Mock(value=b'TestClass')}
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
        mock_die.attributes = {'DW_AT_name': Mock(value=b'OtherClass')}

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
        mock_class_die.attributes = {
            "DW_AT_byte_size": Mock(value=16)
        }
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
        mock_class_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass")
        }
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
        with patch.object(class_parser, 'find_class') as mock_find:
            mock_find.return_value = None  # Class not found case

            result = class_parser.build_inheritance_hierarchy("NonExistentClass")

            assert result == []
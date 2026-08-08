"""
Comprehensive unit tests for ClassParser module.
Tests the core DWARF class parsing functionality with proper mocks.
"""

from unittest.mock import Mock

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
            "DW_AT_accessibility": Mock(value=2),
            "DW_AT_bit_size": Mock(value=3),
            "DW_AT_data_bit_offset": Mock(value=4),
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
        assert result.kind == "class"
        assert result.qualified_name == "TestClass"
        assert result.byte_size == 24
        assert len(result.members) == 1
        assert result.members[0].name == "m_value"
        assert result.members[0].type_name == "int"
        assert result.members[0].type_offset == 0x2000  # Verify offset captured
        assert result.members[0].access == "protected"
        assert result.members[0].bit_size == 3
        assert result.members[0].bit_offset == 4

    @pytest.mark.unit
    def test_parse_class_info_preserves_nested_class_scope(self, class_parser):
        """Nested class definitions retain their containing qualified name."""
        parent_die = Mock()
        parent_die.tag = "DW_TAG_class_type"
        parent_die.attributes = {
            "DW_AT_name": Mock(value=b"rTutorialDialogMessage"),
            "DW_AT_byte_size": Mock(value=152),
        }
        parent_die.offset = 0x1000
        parent_die.get_parent.return_value = None

        nested_die = Mock()
        nested_die.tag = "DW_TAG_class_type"
        nested_die.attributes = {
            "DW_AT_name": Mock(value=b"cDialogPage"),
            "DW_AT_byte_size": Mock(value=32),
        }
        nested_die.offset = 0x1010
        nested_die.get_parent.return_value = parent_die
        nested_die.iter_children.return_value = []
        parent_die.iter_children.return_value = [nested_die]

        result = class_parser.parse_class_info(Mock(cu_offset=0x2000), parent_die)

        assert len(result.nested_classes) == 1
        assert result.nested_classes[0].name == "cDialogPage"
        assert result.nested_classes[0].qualified_name == ("rTutorialDialogMessage::cDialogPage")
        assert result.nested_classes[0].containing_type == "rTutorialDialogMessage"

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

    @pytest.mark.unit
    def test_parse_member_uses_opaque_storage_for_same_named_external_type(self, class_parser):
        member = Mock()
        member.tag = "DW_TAG_member"
        member.attributes = {
            "DW_AT_name": Mock(value=b"m_textureObject"),
            "DW_AT_data_member_location": Mock(value=0x20),
            "DW_AT_type": Mock(value=0x1111),
        }
        parent = Mock(tag="DW_TAG_class_type", offset=0x2000)
        parent.attributes = {"DW_AT_name": Mock(value=b"Texture")}
        member.get_parent.return_value = parent
        target = Mock(tag="DW_TAG_class_type", offset=0x1111)
        target.attributes = {
            "DW_AT_name": Mock(value=b"Texture"),
            "DW_AT_byte_size": Mock(value=32),
        }
        member.get_DIE_from_attribute.return_value = target
        class_parser.type_resolver.resolve_type_name.return_value = "Texture"

        result = class_parser.parse_member(member)

        assert result is not None
        assert result.type_name == "Texture"
        assert result.opaque_storage_size == 32

    @pytest.mark.unit
    def test_parse_member_uses_opaque_storage_for_unresolved_sized_array(self, class_parser):
        member = Mock()
        member.tag = "DW_TAG_member"
        member.attributes = {
            "DW_AT_name": Mock(value=b"m_data"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x1111),
        }
        array_type = Mock(tag="DW_TAG_array_type", offset=0x1111)
        array_type.attributes = {"DW_AT_byte_size": Mock(value=16)}
        member.get_DIE_from_attribute.return_value = array_type
        class_parser.type_resolver.resolve_type_name.return_value = "void[4]"

        result = class_parser.parse_member(member)

        assert result is not None
        assert result.opaque_storage_size == 16

    @pytest.mark.unit
    def test_parse_member_preserves_unresolved_status_without_type_or_size(self, class_parser):
        member = Mock()
        member.tag = "DW_TAG_member"
        member.attributes = {
            "DW_AT_name": Mock(value=b"m_unknown"),
            "DW_AT_data_member_location": Mock(value=0),
        }
        member.offset = 0x2222
        class_parser.type_resolver.resolve_type_name.return_value = "void"

        result = class_parser.parse_member(member)

        assert result is not None
        assert result.type_name == "unknown_type"
        assert result.opaque_storage_size is None

    @pytest.mark.unit
    def test_parse_member_captures_template_argument_type_reference(self, class_parser):
        member = Mock()
        member.tag = "DW_TAG_member"
        member.offset = 0x2000
        member.attributes = {
            "DW_AT_name": Mock(value=b"m_path"),
            "DW_AT_data_member_location": Mock(value=0),
            "DW_AT_type": Mock(value=0x1111),
        }
        template_type = Mock(tag="DW_TAG_class_type", offset=0x1111)
        template_type.attributes = {"DW_AT_name": Mock(value=b"cResPath<rAIFSM>")}
        template_parameter = Mock(tag="DW_TAG_template_type_param", offset=0x1122)
        template_parameter.attributes = {"DW_AT_type": Mock(value=0x1133)}
        argument_type = Mock(tag="DW_TAG_class_type", offset=0x1133)
        argument_type.attributes = {"DW_AT_name": Mock(value=b"rAIFSM")}
        argument_type.iter_children.return_value = []
        template_parameter.get_DIE_from_attribute.return_value = argument_type
        template_type.iter_children.return_value = [template_parameter]
        member.get_DIE_from_attribute.return_value = template_type
        class_parser.type_resolver.resolve_type_name.side_effect = [
            "cResPath<rAIFSM>",
            "rAIFSM",
        ]

        result = class_parser.parse_member(member)

        assert result is not None
        assert [reference.name for reference in result.template_arguments] == ["rAIFSM"]
        assert result.template_arguments[0].die_offset == 0x1133

    @pytest.mark.unit
    def test_parse_method_basic_function(self, class_parser):
        """Test method parsing for basic member functions."""
        # Mock method DIE
        mock_method = Mock()
        mock_method.tag = "DW_TAG_subprogram"
        mock_method.offset = 0x7000
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

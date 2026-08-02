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
    def test_parse_method_decodes_vtable_constu_expression(self, class_parser):
        """Virtual slots are recovered from DW_OP_constu instead of defaulting to zero."""
        mock_method = Mock()
        mock_method.tag = "DW_TAG_subprogram"
        mock_method.offset = 0x7001
        mock_method.attributes = {
            "DW_AT_name": Mock(value=b"load"),
            "DW_AT_virtuality": Mock(value=1),
            "DW_AT_vtable_elem_location": Mock(value=bytes((0x10, 0x05))),
        }
        mock_method.iter_children.return_value = []
        parent_die = Mock()
        parent_die.attributes = {"DW_AT_name": Mock(value=b"TestClass")}
        mock_method.get_parent.return_value = parent_die
        class_parser.type_resolver.resolve_type_name.return_value = "bool"

        method = class_parser.parse_method(mock_method)

        assert method is not None
        assert method.vtable_index == 5

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

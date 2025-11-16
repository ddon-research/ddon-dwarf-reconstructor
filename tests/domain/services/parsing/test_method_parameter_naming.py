#!/usr/bin/env python3

"""Unit tests for method parameter naming behavior."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing.class_parser import ClassParser


@pytest.mark.unit
class TestParameterNaming:
    """Test parameter name extraction and auto-incrementing."""

    @pytest.fixture
    def class_parser(self, mocker):
        """Create ClassParser with mocked dependencies."""
        mock_type_resolver = mocker.Mock()
        mock_dwarf_info = mocker.Mock()
        return ClassParser(mock_type_resolver, mock_dwarf_info)

    def test_parameter_with_name_uses_actual_name(self, class_parser, mocker):
        """Test that parameters with DW_AT_name use the actual name."""
        # Mock TypeChainTraverser
        mocker.patch(
            "ddon_dwarf_reconstructor.domain.services.parsing.class_parser."
            "TypeChainTraverser.get_terminal_type_offset",
            return_value=None,
        )

        # Mock parameter DIE with actual name
        param_die = Mock()
        param_die.tag = "DW_TAG_formal_parameter"
        param_die.attributes = {
            "DW_AT_name": Mock(value=b"output_velocity_error"),
            "DW_AT_type": Mock(value=0x1234),
        }
        param_die.get_parent.return_value = None

        # Mock type resolver
        class_parser.type_resolver.resolve_type_name.return_value = "MtFloat4A &"

        # Parse parameter
        param = class_parser.parse_parameter(param_die, param_index=0)

        assert param is not None
        assert param.name == "output_velocity_error"
        assert param.type_name == "MtFloat4A &"

    def test_parameter_without_name_uses_auto_increment(self, class_parser, mocker):
        """Test that unnamed parameters get auto-incremented names (param1, param2, ...)."""
        # Mock TypeChainTraverser
        mocker.patch(
            "ddon_dwarf_reconstructor.domain.services.parsing.class_parser."
            "TypeChainTraverser.get_terminal_type_offset",
            return_value=None,
        )

        # Mock parameter DIE without name
        param_die = Mock()
        param_die.tag = "DW_TAG_formal_parameter"
        param_die.attributes = {
            "DW_AT_type": Mock(value=0x1234),
        }
        param_die.get_parent.return_value = None

        # Mock type resolver
        class_parser.type_resolver.resolve_type_name.return_value = "u32"

        # Parse multiple parameters with different indices
        param0 = class_parser.parse_parameter(param_die, param_index=0)
        param1 = class_parser.parse_parameter(param_die, param_index=1)
        param2 = class_parser.parse_parameter(param_die, param_index=2)

        assert param0.name == "param1"  # Zero-based index becomes 1-based name
        assert param1.name == "param2"
        assert param2.name == "param3"

    def test_artificial_parameters_marked_correctly(self, class_parser, mocker):
        """Test that artificial parameters (this pointer) are marked with __artificial__."""
        # Mock TypeChainTraverser
        mocker.patch(
            "ddon_dwarf_reconstructor.domain.services.parsing.class_parser."
            "TypeChainTraverser.get_terminal_type_offset",
            return_value=None,
        )

        # Mock artificial parameter DIE (this pointer)
        param_die = Mock()
        param_die.tag = "DW_TAG_formal_parameter"
        param_die.attributes = {
            "DW_AT_artificial": Mock(value=True),
            "DW_AT_type": Mock(value=0x1234),
        }
        param_die.get_parent.return_value = None

        # Mock type resolver
        class_parser.type_resolver.resolve_type_name.return_value = "MyClass*"

        # Parse parameter
        param = class_parser.parse_parameter(param_die, param_index=0)

        assert param is not None
        assert param.name == "__artificial__"
        assert param.type_name == "MyClass*"

    def test_method_with_mixed_parameters(self, class_parser, mocker):
        """Test method with artificial (this) and regular unnamed parameters."""
        # Mock method DIE
        method_die = Mock()
        method_die.tag = "DW_TAG_subprogram"
        method_die.attributes = {
            "DW_AT_name": Mock(value=b"setAllocator"),
        }
        method_die.get_parent.return_value = None

        # Mock artificial this pointer parameter
        this_param = Mock()
        this_param.tag = "DW_TAG_formal_parameter"
        this_param.attributes = {
            "DW_AT_artificial": Mock(value=True),
            "DW_AT_type": Mock(value=0x1000),
        }
        this_param.get_parent.return_value = None

        # Mock regular unnamed parameter
        regular_param = Mock()
        regular_param.tag = "DW_TAG_formal_parameter"
        regular_param.attributes = {
            "DW_AT_type": Mock(value=0x2000),
        }
        regular_param.get_parent.return_value = None

        # Mock iter_children to return both parameters
        method_die.iter_children.return_value = [this_param, regular_param]

        # Mock type resolver
        class_parser.type_resolver.resolve_type_name.side_effect = [
            "void",  # return type
            "MyClass*",  # this pointer
            "u32",  # regular parameter
        ]

        # Mock TypeChainTraverser
        mocker.patch(
            "ddon_dwarf_reconstructor.domain.services.parsing.class_parser."
            "TypeChainTraverser.get_terminal_type_offset",
            return_value=None,
        )

        # Parse method
        method = class_parser.parse_method(method_die)

        assert method is not None
        assert method.name == "setAllocator"
        assert len(method.parameters) == 2

        # First parameter should be artificial (this)
        assert method.parameters[0].name == "__artificial__"
        assert method.parameters[0].type_name == "MyClass*"

        # Second parameter should be param1 (not param2, since artificial doesn't count)
        assert method.parameters[1].name == "param1"
        assert method.parameters[1].type_name == "u32"

    def test_method_with_multiple_unnamed_parameters(self, class_parser, mocker):
        """Test method with multiple unnamed parameters gets sequential numbering."""
        # Mock method DIE
        method_die = Mock()
        method_die.tag = "DW_TAG_subprogram"
        method_die.attributes = {
            "DW_AT_name": Mock(value=b"calculate"),
        }
        method_die.get_parent.return_value = None

        # Create three unnamed parameters
        params = []
        for i in range(3):
            param = Mock()
            param.tag = "DW_TAG_formal_parameter"
            param.attributes = {
                "DW_AT_type": Mock(value=0x1000 + i),
            }
            param.get_parent.return_value = None
            params.append(param)

        method_die.iter_children.return_value = params

        # Mock type resolver
        class_parser.type_resolver.resolve_type_name.side_effect = [
            "void",  # return type
            "int",  # param1
            "float",  # param2
            "double",  # param3
        ]

        # Mock TypeChainTraverser
        mocker.patch(
            "ddon_dwarf_reconstructor.domain.services.parsing.class_parser."
            "TypeChainTraverser.get_terminal_type_offset",
            return_value=None,
        )

        # Parse method
        method = class_parser.parse_method(method_die)

        assert method is not None
        assert len(method.parameters) == 3
        assert method.parameters[0].name == "param1"
        assert method.parameters[1].name == "param2"
        assert method.parameters[2].name == "param3"

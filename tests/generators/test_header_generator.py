"""
Simplified unit tests for HeaderGenerator module.
Tests the core C++ header generation functionality.
"""

import pytest
from unittest.mock import Mock

from ddon_dwarf_reconstructor.generators.header_generator import HeaderGenerator
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo, MethodInfo, ParameterInfo


class TestHeaderGenerator:
    """Test suite for HeaderGenerator functionality."""

    @pytest.fixture
    def header_generator(self):
        """HeaderGenerator instance."""
        return HeaderGenerator()

    @pytest.fixture
    def sample_class(self):
        """Create a sample class for testing."""
        members = [
            MemberInfo(name="m_value", type_name="int", offset=0),
            MemberInfo(name="m_name", type_name="std::string", offset=8)
        ]

        methods = [
            MethodInfo(name="TestClass", return_type="", parameters=[], is_constructor=True),
            MethodInfo(name="getValue", return_type="int", parameters=[]),
            MethodInfo(name="~TestClass", return_type="", parameters=[], is_destructor=True)
        ]

        return ClassInfo(
            name="TestClass",
            byte_size=48,
            members=members,
            methods=methods,
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x1000
        )

    @pytest.mark.unit
    def test_initialization(self, header_generator):
        """Test proper initialization of HeaderGenerator."""
        assert header_generator is not None
        assert hasattr(header_generator, 'generate_header')
        assert hasattr(header_generator, 'generate_hierarchy_header')

    @pytest.mark.unit
    def test_generate_header_basic_class(self, header_generator, sample_class):
        """Test basic header generation for a simple class."""
        header = header_generator.generate_header(sample_class)

        # Check for basic header structure
        assert isinstance(header, str)
        assert len(header) > 0

        # Check for include guards
        assert "#ifndef TESTCLASS_H" in header
        assert "#define TESTCLASS_H" in header
        assert "#endif" in header

        # Check for class definition
        assert "class TestClass" in header

        # Check for members
        assert "m_value" in header
        assert "m_name" in header

        # Check for methods
        assert "TestClass();" in header  # Constructor
        assert "getValue" in header
        assert "~TestClass();" in header  # Destructor

    @pytest.mark.unit
    def test_generate_header_with_inheritance(self, header_generator):
        """Test header generation with inheritance."""
        derived_class = ClassInfo(
            name="DerivedClass",
            byte_size=32,
            members=[MemberInfo("m_derived", "int", 16)],
            methods=[],
            base_classes=["BaseClass"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x2000
        )

        header = header_generator.generate_header(derived_class)

        # Should include inheritance syntax
        assert "class DerivedClass : public BaseClass" in header

    @pytest.mark.unit
    def test_generate_hierarchy_header_empty(self, header_generator):
        """Test hierarchy header generation with empty class list."""
        header = header_generator.generate_hierarchy_header({}, [], "TestClass")

        # Should generate valid header structure
        assert isinstance(header, str)
        assert "#ifndef TESTCLASS_H" in header
        assert "#define TESTCLASS_H" in header
        assert "#endif" in header

    @pytest.mark.unit
    def test_generate_hierarchy_header_single_class(self, header_generator, sample_class):
        """Test hierarchy header generation with single class."""
        classes = {"TestClass": sample_class}
        order = ["TestClass"]
        header = header_generator.generate_hierarchy_header(classes, order, "TestClass")

        # Should include the class
        assert "class TestClass" in header
        assert "TestClass();" in header

    @pytest.mark.unit
    def test_generate_header_with_typedefs(self, header_generator, sample_class):
        """Test header generation with typedef information."""
        typedefs = {
            "u32": "unsigned int",
            "s32": "int"
        }

        header = header_generator.generate_header(sample_class, typedefs=typedefs)

        # Should include typedefs
        assert "typedef unsigned int u32;" in header
        assert "typedef int s32;" in header

    @pytest.mark.unit
    def test_generate_header_empty_class(self, header_generator):
        """Test header generation for empty class."""
        empty_class = ClassInfo(
            name="EmptyClass",
            byte_size=1,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x3000
        )

        header = header_generator.generate_header(empty_class)

        # Should still generate valid header
        assert "class EmptyClass" in header
        assert "#ifndef EMPTYCLASS_H" in header

    @pytest.mark.unit
    def test_generate_header_with_methods(self, header_generator):
        """Test header generation with various method types."""
        methods = [
            MethodInfo(name="MyClass", return_type="", parameters=[], is_constructor=True),
            MethodInfo(name="getValue", return_type="int", parameters=[]),
            MethodInfo(name="setValue", return_type="void", 
                      parameters=[ParameterInfo("value", "int")]),
            MethodInfo(name="~MyClass", return_type="", parameters=[], is_destructor=True)
        ]

        test_class = ClassInfo(
            name="MyClass",
            byte_size=16,
            members=[],
            methods=methods,
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x4000
        )

        header = header_generator.generate_header(test_class)

        # Should include all method types
        assert "MyClass();" in header  # Constructor
        assert "getValue" in header
        assert "setValue" in header
        assert "~MyClass();" in header  # Destructor

    @pytest.mark.unit
    def test_generate_header_metadata_inclusion(self, header_generator, sample_class):
        """Test that metadata is included in generated headers."""
        header = header_generator.generate_header(sample_class, include_metadata=True)

        # Should include metadata comments
        assert "Generated from DWARF debug information" in header
        assert "DIE Offset" in header
        assert "Size:" in header

    @pytest.mark.unit
    def test_generate_header_no_metadata(self, header_generator, sample_class):
        """Test header generation without metadata."""
        header = header_generator.generate_header(sample_class, include_metadata=False)

        # Should not include metadata comments
        assert "Generated from DWARF debug information" not in header
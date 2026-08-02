"""
Simplified unit tests for HeaderGenerator module.
Tests the core C++ header generation functionality.
"""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderGenerator


class TestHeaderGenerator:
    """Test suite for HeaderGenerator functionality."""

    @pytest.fixture
    def mock_dwarf_index(self):
        """Mock DWARF index for testing."""
        return Mock()

    @pytest.fixture
    def header_generator(self, mock_dwarf_index):
        """HeaderGenerator instance with mock dwarf_index."""
        return HeaderGenerator(mock_dwarf_index)

    @pytest.fixture
    def sample_class(self):
        """Create a sample class for testing."""
        members = [
            MemberInfo(name="m_value", type_name="int", offset=0),
            MemberInfo(name="m_name", type_name="std::string", offset=8),
        ]

        methods = [
            MethodInfo(name="TestClass", return_type="", parameters=[], is_constructor=True),
            MethodInfo(name="getValue", return_type="int", parameters=[]),
            MethodInfo(name="~TestClass", return_type="", parameters=[], is_destructor=True),
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
            die_offset=0x1000,
        )

    @pytest.mark.unit
    def test_template_specialization_renders_as_primary_template(self, header_generator):
        """Resolved specializations must not be emitted as illegal class specializations."""
        template_class = ClassInfo(
            name="Box<int>",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5800,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"Box<int>": template_class}, ["Box<int>"], "Box<int>"
        )

        assert "template <typename T>" in header
        assert "class Box" in header
        assert "class Box<int>" not in header

    @pytest.mark.unit
    def test_template_primary_constructor_uses_primary_name(self, header_generator):
        """A specialization's recovered constructor must keep the primary template name."""
        template_class = ClassInfo(
            name="Box<int>",
            byte_size=8,
            members=[],
            methods=[MethodInfo(name="Box", return_type="void")],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5900,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"Box<int>": template_class}, ["Box<int>"], "Box<int>"
        )

        assert "Box();" in header
        assert "void Box();" not in header

    @pytest.mark.unit
    def test_generate_header_with_typedefs(self, header_generator, sample_class):
        """Test header generation with typedef information."""
        typedefs = {"u32": "unsigned int", "s32": "int"}

        header = header_generator.generate_header(sample_class, typedefs=typedefs)

        # Should include typedefs
        assert "typedef unsigned int u32;" in header
        assert "typedef int s32;" in header

    @pytest.mark.unit
    def test_generate_header_does_not_redeclare_standard_size_t(
        self, header_generator, sample_class
    ):
        """Standard size_t must not conflict with the C++ standard headers."""
        header = header_generator.generate_header(
            sample_class,
            typedefs={"size_t": "long unsigned int", "u32": "unsigned int"},
        )

        assert "typedef unsigned int u32;" in header
        assert "typedef long unsigned int size_t;" not in header
        assert "size_t provided by the standard C++ headers" in header

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
            die_offset=0x3000,
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
            MethodInfo(
                name="setValue", return_type="void", parameters=[ParameterInfo("value", "int")]
            ),
            MethodInfo(name="~MyClass", return_type="", parameters=[], is_destructor=True),
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
            die_offset=0x4000,
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

    @pytest.mark.unit
    def test_generate_header_preserves_kind_access_and_bitfield(self, header_generator):
        """Recovered aggregate kind, access, and bitfield width affect declarations."""
        layout = ClassInfo(
            name="Layout",
            byte_size=4,
            members=[
                MemberInfo("public_value", "unsigned int", offset=0, bit_size=3),
                MemberInfo("protected_value", "unsigned int", offset=0, access="protected"),
                MemberInfo("private_value", "unsigned int", offset=0, access="private"),
            ],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5000,
            kind="struct",
        )

        header = header_generator.generate_header(layout, include_metadata=False)

        assert "struct Layout" in header
        assert "unsigned int public_value : 3;" in header
        assert "protected:" in header
        assert "private:" in header

    @pytest.mark.unit
    def test_generate_header_preserves_method_qualifiers(self, header_generator):
        """Method qualifiers and special declaration states are rendered."""
        method = MethodInfo(
            name="read",
            return_type="int",
            parameters=[],
            is_static=True,
            is_const=True,
            is_volatile=True,
            ref_qualifier="&&",
            is_noexcept=True,
            is_deleted=True,
        )
        layout = ClassInfo(
            name="Qualified",
            byte_size=1,
            members=[],
            methods=[method],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x6000,
        )

        header = header_generator.generate_header(layout, include_metadata=False)

        assert "static int read() const volatile && noexcept = delete;" in header

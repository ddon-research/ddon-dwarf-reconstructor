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
    TypeDeclarator,
    TypeReference,
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
    def test_initialization(self, header_generator):
        """Test proper initialization of HeaderGenerator."""
        assert header_generator is not None
        assert hasattr(header_generator, "generate_header")
        assert hasattr(header_generator, "generate_single_file_hierarchy_header")

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
    def test_generate_header_renders_nested_template_argument(self, header_generator):
        """Nested classes are emitted before qualified template member uses."""
        nested_class = ClassInfo(
            name="cDialogPage",
            byte_size=32,
            members=[MemberInfo("m_index", "int", offset=0)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x1010,
            qualified_name="rTutorialDialogMessage::cDialogPage",
        )
        outer_class = ClassInfo(
            name="rTutorialDialogMessage",
            byte_size=152,
            members=[
                MemberInfo(
                    "m_page_info",
                    "MtTypedArray<rTutorialDialogMessage::cDialogPage>",
                    type_offset=0x7000,
                    offset=0x78,
                )
            ],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            nested_classes=[nested_class],
            die_offset=0x1000,
        )
        template_die = Mock(
            tag="DW_TAG_class_type",
            attributes={"DW_AT_name": Mock(value=b"MtTypedArray")},
        )
        header_generator.dwarf_index.get_die_by_offset.return_value = template_die

        header = header_generator.generate_header(outer_class, include_metadata=False)

        assert "class cDialogPage" in header
        assert "template <typename T> class MtTypedArray;" in header
        assert "class MtTypedArray<rTutorialDialogMessage::cDialogPage>;" not in header
        assert "MtTypedArray<cDialogPage> m_page_info;" in header

    @pytest.mark.unit
    def test_generate_header_declares_template_argument_from_structured_evidence(
        self, header_generator
    ):
        outer_class = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[
                MemberInfo(
                    "m_path",
                    "cResPath<rAIFSM>",
                    type_offset=0x1000,
                    template_arguments=(
                        TypeReference(TypeDeclarator("rAIFSM"), die_offset=0x2000),
                    ),
                    offset=0,
                )
            ],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x3000,
        )
        template_die = Mock(
            tag="DW_TAG_class_type",
            attributes={"DW_AT_name": Mock(value=b"cResPath<rAIFSM>")},
        )
        argument_die = Mock(
            tag="DW_TAG_class_type",
            attributes={"DW_AT_name": Mock(value=b"rAIFSM")},
        )
        header_generator.dwarf_index.get_die_by_offset.side_effect = lambda offset: {
            0x1000: template_die,
            0x2000: argument_die,
        }.get(offset)

        header = header_generator.generate_header(outer_class, include_metadata=False)

        assert "class rAIFSM;" in header
        assert header.index("class rAIFSM;") < header.index("cResPath<rAIFSM> m_path;")

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
            die_offset=0x2000,
        )

        header = header_generator.generate_header(derived_class)

        # Should include inheritance syntax
        assert "class DerivedClass : public BaseClass" in header

    @pytest.mark.unit
    def test_hierarchy_qualifies_nested_base_from_die_identity(self, header_generator):
        """Nested bases use their enclosing aggregate when rendered out of scope."""
        nested_base = ClassInfo(
            name="cInGameGroupManager",
            byte_size=64,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x2000,
            qualified_name="cZoneLayout::cInGameGroupManager",
            containing_type="cZoneLayout",
        )
        derived_class = ClassInfo(
            name="cGroupManager",
            byte_size=32,
            members=[],
            methods=[],
            base_classes=["cInGameGroupManager"],
            base_class_offsets=[0x2000],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x3000,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"cGroupManager": derived_class},
            ["cGroupManager"],
            "cGroupManager",
            include_metadata=False,
            base_type_infos={"cInGameGroupManager": nested_base},
        )

        assert "class cGroupManager : public cZoneLayout::cInGameGroupManager" in header

    @pytest.mark.unit
    def test_generate_single_file_hierarchy_header_empty(self, header_generator):
        """Test single-file hierarchy header generation with empty class list."""
        header = header_generator.generate_single_file_hierarchy_header({}, [], "TestClass")

        # Should generate valid header structure
        assert isinstance(header, str)
        assert "#ifndef TESTCLASS_H" in header
        assert "#define TESTCLASS_H" in header
        assert "#endif" in header

    @pytest.mark.unit
    def test_generate_single_file_hierarchy_header_single_class(
        self, header_generator, sample_class
    ):
        """Test single-file hierarchy header generation with single class."""
        classes = {"TestClass": sample_class}
        order = ["TestClass"]
        header = header_generator.generate_single_file_hierarchy_header(classes, order, "TestClass")

        # Should include the class
        assert "class TestClass" in header
        assert "TestClass();" in header

    @pytest.mark.unit
    def test_hierarchy_header_includes_external_definition_dependencies(self, header_generator):
        derived_class = ClassInfo(
            name="DerivedClass",
            byte_size=16,
            members=[],
            methods=[],
            base_classes=["BaseClass"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x2000,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"DerivedClass": derived_class},
            ["DerivedClass"],
            "DerivedClass",
            include_metadata=False,
            dependency_headers={"BaseClass": "BaseClass.h"},
        )

        assert '#include "BaseClass.h"' in header
        assert header.index('#include "BaseClass.h"') < header.index(
            "class DerivedClass : public BaseClass"
        )

    @pytest.mark.unit
    def test_generate_single_file_hierarchy_header_emits_valid_dependency_declarations(
        self, header_generator
    ):
        """Hierarchy output must not duplicate declaration syntax."""
        base_class = ClassInfo(
            name="BaseClass",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x2000,
        )
        value_type = ClassInfo(
            name="ValueType",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x3000,
        )
        derived_class = ClassInfo(
            name="DerivedClass",
            byte_size=16,
            members=[MemberInfo("m_value", "ValueType", offset=8, type_offset=0x3000)],
            methods=[],
            base_classes=["BaseClass"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x4000,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {
                "BaseClass": base_class,
                "ValueType": value_type,
                "DerivedClass": derived_class,
            },
            ["BaseClass", "DerivedClass"],
            "DerivedClass",
        )

        assert "class class" not in header
        assert ";;" not in header
        assert header.index("class ValueType\n{") < header.index(
            "class DerivedClass : public BaseClass\n{"
        )
        assert "class DerivedClass : public BaseClass" in header
        assert "ValueType m_value;" in header
        assert header.count("class ValueType\n{") == 1
        assert header.count("class DerivedClass : public BaseClass\n{") == 1


@pytest.mark.unit
def test_template_forward_declaration_matches_multiple_argument_arity() -> None:
    declaration = HeaderGenerator._template_forward_declaration("Box<Pair<int, float>, 4>")

    assert declaration == "template <typename T, auto N1> class Box;"


@pytest.mark.unit
def test_nested_template_arguments_use_template_forward_declarations() -> None:
    declarations = HeaderGenerator._template_argument_forward_declarations(
        "MtStlVector<s8, MtStlAllocator<signed char>>", set()
    )

    assert "template <typename T> class MtStlAllocator;" in declarations
    assert "class MtStlAllocator;" not in declarations

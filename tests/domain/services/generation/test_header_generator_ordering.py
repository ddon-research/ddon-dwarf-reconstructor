"""
Simplified unit tests for HeaderGenerator module.
Tests the core C++ header generation functionality.
"""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
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
    def test_hierarchy_orders_nested_class_bases_before_containing_class(self, header_generator):
        """Nested class inheritance must not depend on a later definition."""
        dti_class = ClassInfo(
            name="MtDTI",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5000,
        )
        nested_class = ClassInfo(
            name="MyDTI",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=["MtDTI"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5100,
        )
        outer_class = ClassInfo(
            name="MtObject",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            nested_classes=[nested_class],
            die_offset=0x5200,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"MtObject": outer_class, "MtDTI": dti_class},
            ["MtObject"],
            "MtObject",
            include_metadata=False,
        )

        assert header.index("class MtDTI") < header.index("class MtObject")
        assert "class MyDTI : public MtDTI" in header

    @pytest.mark.unit
    def test_by_value_dependency_cycles_are_blocking(self, header_generator) -> None:
        with pytest.raises(ValueError, match="cyclic by-value dependencies"):
            header_generator._stable_topological_order({"A": {"B"}, "B": {"A"}}, ["A", "B"])

    @pytest.mark.unit
    def test_hierarchy_declares_opaque_typedef_targets(self, header_generator):
        """Typedefs to external opaque types must be declared before the alias."""
        sample_class = ClassInfo(
            name="OpaqueOwner",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5300,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"OpaqueOwner": sample_class},
            ["OpaqueOwner"],
            "OpaqueOwner",
            typedefs={"OpaqueHandle": "pthread_mutex*"},
            include_metadata=False,
        )

        assert "class pthread_mutex;" in header
        assert header.index("class pthread_mutex;") < header.index(
            "typedef pthread_mutex* OpaqueHandle;"
        )

    @pytest.mark.unit
    def test_conversion_operator_omits_return_type(self, header_generator):
        """C++ conversion operators must not repeat their return type."""
        class_info = ClassInfo(
            name="Convertible",
            byte_size=8,
            members=[],
            methods=[MethodInfo(name="operator const char *", return_type="MT_CTSTR")],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5400,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "operator const char *();" in header
        assert "MT_CTSTR operator const char *" not in header

    @pytest.mark.unit
    def test_duplicate_method_signatures_are_emitted_once(self, header_generator):
        """Repeated DWARF entries must not create illegal return-only overloads."""
        class_info = ClassInfo(
            name="DuplicateMethods",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="cast",
                    return_type="MtObject*",
                    parameters=[ParameterInfo(name="dti", type_name="const MtDTI&")],
                ),
                MethodInfo(
                    name="cast",
                    return_type="const MtObject*",
                    parameters=[ParameterInfo(name="dti", type_name="const MtDTI&")],
                ),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5500,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert header.count("cast(const MtDTI& dti);") == 1

    @pytest.mark.unit
    def test_nested_struct_pointer_members_receive_forward_declarations(self, header_generator):
        """Pointer-only members in nested structs must name declared aggregate types."""
        class_info = ClassInfo(
            name="Layout",
            byte_size=16,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[
                StructInfo(
                    name="Buffer",
                    byte_size=8,
                    members=[MemberInfo("items", "Item*", offset=0)],
                )
            ],
            unions=[],
            die_offset=0x5600,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "class Item;" in header
        assert "Item* items;" in header

    @pytest.mark.unit
    def test_enum_method_types_are_defined_before_method_users(self, header_generator):
        """Method signatures using recovered enums must compile without external stubs."""
        class_info = ClassInfo(
            name="Texture",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="setMode", return_type="void", parameters=[ParameterInfo("mode", "Mode")]
                )
            ],
            base_classes=[],
            enums=[
                EnumInfo(
                    name="Mode",
                    byte_size=4,
                    enumerators=[EnumeratorInfo(name="MODE_A", value=0)],
                )
            ],
            nested_structs=[],
            unions=[],
            die_offset=0x5700,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "enum class Mode" in header
        assert "void setMode(Mode mode);" in header

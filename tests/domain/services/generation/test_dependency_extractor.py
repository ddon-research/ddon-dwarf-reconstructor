#!/usr/bin/env python3

"""Unit tests for DependencyExtractor service."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
    UnionInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation.dependency_extractor import (
    DependencyExtractor,
)


@pytest.mark.unit
class TestDependencyExtractor:
    """Test suite for DependencyExtractor."""

    @pytest.fixture
    def mock_dwarf_index(self):
        """Create mock DWARF index service."""
        return Mock()

    @pytest.fixture
    def extractor(self, mock_dwarf_index):
        """Create DependencyExtractor instance."""
        return DependencyExtractor(mock_dwarf_index)

    def test_extract_dependencies_from_members(self, extractor):
        """Test extracting dependencies from class members."""
        class_info = ClassInfo(
            name="TestClass",
            members=[
                MemberInfo(
                    name="m_int",
                    type_name="int",
                    type_offset=0x1000,
                    offset=0,
                ),
                MemberInfo(
                    name="m_obj",
                    type_name="MtObject*",
                    type_offset=0x2000,
                    offset=8,
                ),
            ],
            methods=[],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=16,
        )

        dependencies = extractor.extract_dependencies(class_info)

        assert dependencies == {0x1000, 0x2000}

    def test_extract_dependencies_from_methods(self, extractor):
        """Test extracting dependencies from method signatures."""
        class_info = ClassInfo(
            name="TestClass",
            members=[],
            methods=[
                MethodInfo(
                    name="getValue",
                    return_type="int",
                    return_type_offset=0x3000,
                    parameters=[
                        ParameterInfo(
                            name="param1",
                            type_name="float",
                            type_offset=0x4000,
                        ),
                        ParameterInfo(
                            name="param2",
                            type_name="MtObject&",
                            type_offset=0x5000,
                        ),
                    ],
                    is_virtual=False,
                ),
            ],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=8,
        )

        dependencies = extractor.extract_dependencies(class_info)

        assert dependencies == {0x3000, 0x4000, 0x5000}

    def test_extract_dependencies_from_nested_structs(self, extractor):
        """Test extracting dependencies from nested structures."""
        nested_struct = StructInfo(
            name="NestedStruct",
            members=[
                MemberInfo(
                    name="x",
                    type_name="float",
                    type_offset=0x6000,
                    offset=0,
                ),
            ],
            byte_size=4,
        )

        class_info = ClassInfo(
            name="TestClass",
            members=[],
            methods=[],
            nested_structs=[nested_struct],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=8,
        )

        dependencies = extractor.extract_dependencies(class_info)

        assert 0x6000 in dependencies

    def test_extract_dependencies_from_unions(self, extractor):
        """Test extracting dependencies from unions."""
        union = UnionInfo(
            name="TestUnion",
            members=[
                MemberInfo(
                    name="int_val",
                    type_name="int",
                    type_offset=0x7000,
                    offset=0,
                ),
                MemberInfo(
                    name="float_val",
                    type_name="float",
                    type_offset=0x8000,
                    offset=0,
                ),
            ],
            nested_structs=[],
            byte_size=4,
        )

        class_info = ClassInfo(
            name="TestClass",
            members=[],
            methods=[],
            nested_structs=[],
            unions=[union],
            enums=[],
            base_classes=[],
            byte_size=8,
        )

        dependencies = extractor.extract_dependencies(class_info)

        assert dependencies == {0x7000, 0x8000}

    def test_extract_dependencies_handles_none_offsets(self, extractor):
        """Test that None offsets are gracefully skipped."""
        class_info = ClassInfo(
            name="TestClass",
            members=[
                MemberInfo(
                    name="m_int",
                    type_name="int",
                    type_offset=None,  # No offset captured
                    offset=0,
                ),
            ],
            methods=[],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=4,
        )

        dependencies = extractor.extract_dependencies(class_info)

        assert dependencies == set()

    def test_filter_resolvable_types_includes_classes(self, extractor, mock_dwarf_index):
        """Test that classes are included in resolvable types."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"MtObject")}

        mock_dwarf_index.get_die_by_offset.return_value = mock_die

        offsets = {0x1000}
        resolvable = extractor.filter_resolvable_types(offsets)

        assert resolvable == {0x1000}

    def test_filter_resolvable_types_excludes_enums(self, extractor, mock_dwarf_index):
        """Test that enums are excluded from resolvable types."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_enumeration_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"MyEnum")}

        mock_dwarf_index.get_die_by_offset.return_value = mock_die

        offsets = {0x1000}
        resolvable = extractor.filter_resolvable_types(offsets)

        assert resolvable == set()

    def test_filter_resolvable_types_excludes_primitives(self, extractor, mock_dwarf_index):
        """Test that primitive types are excluded from resolvable types."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_base_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"int")}

        mock_dwarf_index.get_die_by_offset.return_value = mock_die

        offsets = {0x1000}
        resolvable = extractor.filter_resolvable_types(offsets)

        assert resolvable == set()

    def test_get_type_name(self, extractor, mock_dwarf_index):
        """Test getting type name from offset."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"MtObject")}

        mock_dwarf_index.get_die_by_offset.return_value = mock_die

        type_name = extractor.get_type_name(0x1000)

        assert type_name == "MtObject"

    def test_get_type_name_returns_none_for_invalid_offset(
        self, extractor, mock_dwarf_index
    ):
        """Test that get_type_name returns None for invalid offsets."""
        mock_dwarf_index.get_die_by_offset.return_value = None

        type_name = extractor.get_type_name(0x9999)

        assert type_name is None

    def test_is_simple_type_small_struct(self, extractor):
        """Test that small structs are considered simple types."""
        class_info = ClassInfo(
            name="SmallStruct",
            members=[
                MemberInfo(name="x", type_name="float", type_offset=0x1000, offset=0),
                MemberInfo(name="y", type_name="float", type_offset=0x1000, offset=4),
            ],
            methods=[],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=8,
        )

        assert extractor.is_simple_type(0x1000, class_info) is True

    def test_is_simple_type_large_struct(self, extractor):
        """Test that large structs are not considered simple types."""
        class_info = ClassInfo(
            name="LargeStruct",
            members=[MemberInfo(name=f"m{i}", type_name="int", offset=i * 4) for i in range(20)],
            methods=[],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=1024,
        )

        assert extractor.is_simple_type(0x1000, class_info) is False

    def test_extract_dependencies_handles_none_parameters(self, extractor):
        """Test that methods with None parameters are handled gracefully."""
        class_info = ClassInfo(
            name="TestClass",
            members=[],
            methods=[
                MethodInfo(
                    name="constructor",
                    return_type="",
                    return_type_offset=None,
                    parameters=None,  # No parameters
                    is_constructor=True,
                ),
            ],
            nested_structs=[],
            unions=[],
            enums=[],
            base_classes=[],
            byte_size=8,
        )

        # Should not raise exception
        dependencies = extractor.extract_dependencies(class_info)

        assert isinstance(dependencies, set)

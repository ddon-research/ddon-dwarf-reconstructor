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

    def test_structural_closure_excludes_method_signature_types(self, extractor):
        """Layout export must not expand transitively through every method signature."""
        class_info = ClassInfo(
            name="TestClass",
            members=[MemberInfo(name="m_obj", type_name="MtObject", type_offset=0x2000)],
            methods=[
                MethodInfo(
                    name="load",
                    return_type="Result",
                    return_type_offset=0x3000,
                    parameters=[
                        ParameterInfo(name="stream", type_name="MtStream&", type_offset=0x4000)
                    ],
                )
            ],
            byte_size=8,
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
        )

        dependencies = extractor.extract_dependencies(class_info, include_method_signatures=False)

        assert dependencies == {0x2000}

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

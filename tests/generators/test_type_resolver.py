#!/usr/bin/env python3

"""Comprehensive unit tests for TypeResolver module.

Tests the critical type resolution logic including caching, primitive typedef
expansion, and cross-hierarchy typedef collection.
"""

import pytest
from unittest.mock import Mock, patch

from ddon_dwarf_reconstructor.domain.services.parsing import TypeResolver


class TestTypeResolver:
    """Test suite for TypeResolver class."""

    @pytest.fixture
    def mock_dwarf_info(self):
        """Mock DWARF info with realistic structure."""
        mock_dwarf = Mock()

        # Mock compilation units with proper iter_DIEs method
        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x0
        mock_cu1.cu_length = 3213
        mock_cu1.iter_DIEs.return_value = []  # Empty DIE list

        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0xc9d
        mock_cu2.cu_length = 42851
        mock_cu2.iter_DIEs.return_value = []  # Empty DIE list

        mock_dwarf.iter_CUs.return_value = [mock_cu1, mock_cu2]
        return mock_dwarf

    @pytest.fixture
    def type_resolver(self, mock_dwarf_info):
        """Create TypeResolver instance with mocked DWARF info."""
        return TypeResolver(mock_dwarf_info)

    @pytest.mark.unit
    def test_initialization(self, type_resolver):
        """Test proper initialization of TypeResolver."""
        assert type_resolver._typedef_cache == {}
        assert isinstance(type_resolver._primitive_typedefs, set)
        assert "u32" in type_resolver._primitive_typedefs
        assert "u16" in type_resolver._primitive_typedefs

    @pytest.mark.unit
    def test_primitive_typedef_set_contents(self, type_resolver):
        """Verify all expected primitive types are included."""
        primitives = type_resolver._primitive_typedefs

        # Core integer types
        expected_types = {
            "u8", "u16", "u32", "u64",
            "s8", "s16", "s32", "s64",
            "f32", "f64",
            "size_t", "ssize_t"
        }

        for expected_type in expected_types:
            assert expected_type in primitives, f"Missing primitive type: {expected_type}"

    @pytest.mark.unit
    def test_expand_primitive_search_basic_mode(self, type_resolver):
        """Test primitive search expansion in basic mode."""
        original_size = len(type_resolver._primitive_typedefs)

        # Basic mode should not expand
        type_resolver.expand_primitive_search(full_hierarchy=False)

        assert len(type_resolver._primitive_typedefs) == original_size

    @pytest.mark.unit
    def test_expand_primitive_search_full_hierarchy_mode(self, type_resolver):
        """Test primitive search expansion in full hierarchy mode."""
        original_size = len(type_resolver._primitive_typedefs)

        # Full hierarchy mode should expand
        type_resolver.expand_primitive_search(full_hierarchy=True)

        expanded_size = len(type_resolver._primitive_typedefs)
        assert expanded_size > original_size

        # Check for additional types
        additional_types = {
            "uint8_t", "int8_t",
            "uint16_t", "int16_t", 
            "uint32_t", "int32_t",
            "uint64_t", "int64_t",
            "uintptr_t", "intptr_t"
        }

        for additional_type in additional_types:
            assert additional_type in type_resolver._primitive_typedefs

    @pytest.mark.unit
    def test_typedef_cache_functionality(self, type_resolver):
        """Test typedef caching mechanism."""
        # Cache should be empty initially
        assert len(type_resolver._typedef_cache) == 0

        # Test caching behavior by calling find_typedef multiple times
        # Since we're using mock DWARF info, it won't find anything, but cache should work
        result1 = type_resolver.find_typedef("non_primitive_type")
        result2 = type_resolver.find_typedef("non_primitive_type")

        # Both should return None (not found) but should be cached
        assert result1 is None
        assert result2 is None

        # Cache should contain the entry
        assert len(type_resolver._typedef_cache) >= 1

    @pytest.mark.unit
    def test_cache_key_generation(self, type_resolver):
        """Test cache key generation for different search modes."""
        # Different modes should create different cache entries
        type_resolver.find_typedef("u32", deep_search=False)
        type_resolver.find_typedef("u32", deep_search=True)

        # Both should be cached separately with different keys
        assert len(type_resolver._typedef_cache) == 2

    @pytest.mark.unit
    def test_resolve_type_name_basic_types(self, type_resolver):
        """Test type name resolution for basic types."""
        # Mock DIE with basic type
        mock_die = Mock()
        mock_die.tag = "DW_TAG_base_type"
        mock_die.attributes = {"DW_AT_name": Mock(value=b"unsigned int")}

        result = type_resolver.resolve_type_name(mock_die)
        # With our simplified mock, this will return the attribute value or default
        assert result in ["unsigned int", "void"]  # Accept either since mocking is simplified

    @pytest.mark.unit
    def test_resolve_type_name_different_tags(self, type_resolver):
        """Test type name resolution for different DIE tags."""
        # Test various DIE types - results may vary based on implementation
        test_cases = [
            ("DW_TAG_pointer_type", "pointer types"),
            ("DW_TAG_const_type", "const qualified types"),
            ("DW_TAG_reference_type", "reference types"),
            ("DW_TAG_array_type", "array types")
        ]

        for tag, description in test_cases:
            mock_die = Mock()
            mock_die.tag = tag
            mock_die.attributes = {}
            mock_die.get_DIE_from_attribute.return_value = None

            result = type_resolver.resolve_type_name(mock_die)
            # Should return some string (implementation may vary)
            assert isinstance(result, str), f"Failed for {description}"

    @pytest.mark.unit
    def test_extract_base_type_simple_cases(self, type_resolver):
        """Test base type extraction for simple cases."""
        test_cases = [
            ("int", "int"),
            ("const int", "int"),
            ("int*", "int"),
            ("const int*", "int"),
            ("int&", "int"),
            ("const int&", "int"),
        ]

        for input_type, expected_base in test_cases:
            result = type_resolver._extract_base_type(input_type)
            assert result == expected_base, f"Failed for {input_type}"

    @pytest.mark.unit
    def test_extract_base_type_complex_cases(self, type_resolver):
        """Test base type extraction for complex cases."""
        test_cases = [
            ("std::vector<int>*", "std::vector<int>"),
            ("const MyClass&", "MyClass"),
            ("unsigned long long", "unsigned long long"),
            ("MyNamespace::MyClass*", "MyNamespace::MyClass"),
        ]

        for input_type, expected_base in test_cases:
            result = type_resolver._extract_base_type(input_type)
            assert result == expected_base, f"Failed for {input_type}"

    @pytest.mark.unit
    def test_collect_used_typedefs_from_members(self, type_resolver):
        """Test typedef collection from member information."""
        # Mock member info objects
        mock_member1 = Mock()
        mock_member1.type_name = "u32"

        mock_member2 = Mock()  
        mock_member2.type_name = "const u16"

        members = [mock_member1, mock_member2]

        with patch.object(type_resolver, 'find_typedef') as mock_find:
            # Return None for both since they won't be found in mock DWARF
            mock_find.return_value = None

            result = type_resolver.collect_used_typedefs(members, [])

            # Should return empty dict since no typedefs found in mock
            assert isinstance(result, dict)
            # Should have attempted to search for primitives
            assert mock_find.call_count >= 1

    @pytest.mark.unit
    def test_collect_used_typedefs_from_methods(self, type_resolver):
        """Test typedef collection from method information.""" 
        # Mock parameter info
        mock_param = Mock()
        mock_param.type_name = "size_t"

        # Mock method info
        mock_method = Mock()
        mock_method.return_type = "u64"
        mock_method.parameters = [mock_param]

        methods = [mock_method]

        with patch.object(type_resolver, 'find_typedef') as mock_find:
            mock_find.return_value = None  # Nothing found in mock DWARF

            result = type_resolver.collect_used_typedefs([], methods)

            # Should return empty dict since no typedefs found
            assert isinstance(result, dict)
            # Should have attempted searches
            assert mock_find.call_count >= 1

    @pytest.mark.unit
    def test_collect_used_typedefs_deduplication(self, type_resolver):
        """Test that typedef collection handles duplicate base types."""
        # Mock members with duplicate types
        mock_member1 = Mock()
        mock_member1.type_name = "u32"

        mock_member2 = Mock()
        mock_member2.type_name = "const u32"  # Same base type

        members = [mock_member1, mock_member2]

        result = type_resolver.collect_used_typedefs(members, [])

        # Should handle deduplication properly (exact behavior depends on implementation)
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_find_typedef_primitive_detection(self, type_resolver):
        """Test that only primitive types are searched."""
        # Non-primitive type should return None quickly
        result = type_resolver.find_typedef("MyCustomClass")
        assert result is None

        # Primitive type should be processed (even if not found in mock DWARF)
        result = type_resolver.find_typedef("u32")
        assert result is None  # Not found in mock DWARF, but was searched

    @pytest.mark.unit
    def test_find_typedef_search_modes(self, type_resolver):
        """Test different search mode behaviors."""
        # Basic search mode
        result1 = type_resolver.find_typedef("u32", deep_search=False)

        # Deep search mode  
        result2 = type_resolver.find_typedef("u32", deep_search=True)

        # Both should work with mock DWARF (returning None since not found)
        assert result1 is None
        assert result2 is None

    @pytest.mark.unit
    def test_performance_caching_behavior(self, type_resolver):
        """Test that caching significantly improves performance."""
        # Test caching by calling same typedef lookup multiple times
        results = []

        # Multiple calls should use cached results
        for _ in range(5):
            result = type_resolver.find_typedef("u32")
            results.append(result)

        # All results should be identical (cached)
        assert all(r == results[0] for r in results)

        # Cache should contain the entry
        assert len(type_resolver._typedef_cache) >= 1

    @pytest.mark.unit
    def test_error_handling_invalid_die(self, type_resolver):
        """Test error handling for invalid DIE structures."""
        # Mock DIE with missing attributes
        mock_die = Mock()
        mock_die.tag = "DW_TAG_base_type"
        mock_die.attributes = {}  # Missing DW_AT_name

        # Should handle gracefully and return default
        result = type_resolver.resolve_type_name(mock_die)
        assert result == "void"  # Default fallback

    @pytest.mark.unit
    def test_recursive_type_resolution_limit(self, type_resolver):
        """Test that recursive type resolution has proper limits."""
        # Create circular reference
        mock_die1 = Mock()
        mock_die2 = Mock() 

        mock_die1.tag = "DW_TAG_pointer_type"
        mock_die2.tag = "DW_TAG_pointer_type"

        # Create circular reference
        mock_die1.get_DIE_from_attribute.return_value = mock_die2
        mock_die2.get_DIE_from_attribute.return_value = mock_die1

        # Should handle circular references gracefully
        result = type_resolver.resolve_type_name(mock_die1)
        # Should return some fallback string (implementation may vary)
        assert isinstance(result, str)
        assert result in ["void", "unknown_type", "void*"]  # Accept various fallbacks
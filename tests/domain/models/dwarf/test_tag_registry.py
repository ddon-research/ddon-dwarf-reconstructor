"""Test the DWARF tag registry and cache migration functionality."""

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf.tag_registry import (
    DwarfTagCategory,
    DwarfTagRegistry,
)


@pytest.mark.unit
class TestDwarfTagRegistry:
    """Test DWARF tag registry functionality."""
    
    def test_all_searchable_tags_include_expected_types(self):
        """Test that all expected tag types are searchable."""
        expected_tags = {
            "DW_TAG_class_type",
            "DW_TAG_structure_type", 
            "DW_TAG_union_type",
            "DW_TAG_typedef",
            "DW_TAG_enumeration_type",
            "DW_TAG_base_type",
            "DW_TAG_namespace",
            "DW_TAG_array_type",
        }
        
        assert DwarfTagRegistry.ALL_SEARCHABLE_TAGS == expected_tags
    
    def test_tag_to_category_mapping(self):
        """Test tag to category mapping."""
        assert DwarfTagRegistry.get_tag_category("DW_TAG_class_type") == DwarfTagCategory.CLASS_LIKE
        assert DwarfTagRegistry.get_tag_category("DW_TAG_typedef") == DwarfTagCategory.TYPE_DEF
        assert DwarfTagRegistry.get_tag_category("DW_TAG_namespace") == DwarfTagCategory.NAMESPACE
        assert DwarfTagRegistry.get_tag_category("DW_TAG_unknown") == DwarfTagCategory.OTHER
    
    def test_category_to_tags_mapping(self):
        """Test category to tags reverse mapping."""
        class_tags = DwarfTagRegistry.get_tags_for_category(DwarfTagCategory.CLASS_LIKE)
        expected_class_tags = frozenset([
            "DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"
        ])
        assert class_tags == expected_class_tags
    
    def test_legacy_type_mapping(self):
        """Test legacy type name to tags mapping."""
        # Test class mapping
        class_tags = DwarfTagRegistry.get_tags_for_legacy_type("class")
        expected_class_tags = frozenset(["DW_TAG_class_type", "DW_TAG_structure_type"])
        assert class_tags == expected_class_tags
        
        # Test typedef mapping
        typedef_tags = DwarfTagRegistry.get_tags_for_legacy_type("typedef")
        expected_typedef_tags = frozenset(["DW_TAG_typedef"])
        assert typedef_tags == expected_typedef_tags
        
        # Test primitive type mapping (should include both typedef and base_type)
        primitive_tags = DwarfTagRegistry.get_tags_for_legacy_type("primitive_type")
        expected_primitive_tags = frozenset(["DW_TAG_typedef", "DW_TAG_base_type"])
        assert primitive_tags == expected_primitive_tags
        
        # Test unknown legacy type
        unknown_tags = DwarfTagRegistry.get_tags_for_legacy_type("unknown_type")
        assert unknown_tags == frozenset()
    
    def test_is_searchable_tag(self):
        """Test searchable tag checking."""
        assert DwarfTagRegistry.is_searchable_tag("DW_TAG_class_type") is True
        assert DwarfTagRegistry.is_searchable_tag("DW_TAG_typedef") is True
        assert DwarfTagRegistry.is_searchable_tag("DW_TAG_namespace") is True
        assert DwarfTagRegistry.is_searchable_tag("DW_TAG_unknown") is False
        assert DwarfTagRegistry.is_searchable_tag("some_random_tag") is False
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        # Should use the tag itself as the cache key for consistency
        assert DwarfTagRegistry.get_cache_key("DW_TAG_class_type") == "DW_TAG_class_type"
        assert DwarfTagRegistry.get_cache_key("DW_TAG_typedef") == "DW_TAG_typedef"
    
    def test_human_readable_names(self):
        """Test human-readable name generation."""
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_class_type") == "class"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_structure_type") == "struct"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_union_type") == "union"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_typedef") == "typedef"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_enumeration_type") == "enum"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_namespace") == "namespace"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_base_type") == "base_type"
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_array_type") == "array"
        
        # Unknown tag should return itself
        assert DwarfTagRegistry.get_human_readable_name("DW_TAG_unknown") == "DW_TAG_unknown"
    
    def test_comprehensive_mapping_coverage(self):
        """Test that all searchable tags have proper mappings."""
        for tag in DwarfTagRegistry.ALL_SEARCHABLE_TAGS:
            # Each tag should have a category
            category = DwarfTagRegistry.get_tag_category(tag)
            assert category != DwarfTagCategory.OTHER, f"Tag {tag} should have a proper category"
            
            # Each tag should be marked as searchable
            assert DwarfTagRegistry.is_searchable_tag(tag), f"Tag {tag} should be searchable"
            
            # Each tag should have a human-readable name
            human_name = DwarfTagRegistry.get_human_readable_name(tag)
            assert human_name != tag or tag.startswith("DW_TAG_"), f"Tag {tag} should have human name"
    
    def test_legacy_backward_compatibility(self):
        """Test that all legacy types are properly mapped."""
        legacy_types = [
            "class", "struct", "union", "typedef", "base_type",
            "enum", "namespace", "primitive_type"
        ]
        
        for legacy_type in legacy_types:
            tags = DwarfTagRegistry.get_tags_for_legacy_type(legacy_type)
            assert len(tags) > 0, f"Legacy type '{legacy_type}' should map to at least one tag"
            
            # All mapped tags should be searchable
            for tag in tags:
                assert DwarfTagRegistry.is_searchable_tag(tag), f"Mapped tag {tag} should be searchable"
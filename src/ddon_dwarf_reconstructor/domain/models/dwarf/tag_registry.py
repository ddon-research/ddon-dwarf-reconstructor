"""Centralized DWARF tag management and mapping.

This module provides unified tag handling across the entire application,
ensuring consistency in tag-to-type mappings and cache keys.
"""

from enum import Enum


class DwarfTagCategory(Enum):
    """Categories of DWARF tags for logical grouping."""

    CLASS_LIKE = "class_like"  # Classes, structs, unions
    TYPE_DEF = "type_def"  # Type definitions
    BASE_TYPE = "base_type"  # Primitive types
    ENUM_TYPE = "enum_type"  # Enumerations
    NAMESPACE = "namespace"  # Namespaces
    ARRAY_TYPE = "array_type"  # Arrays
    OTHER = "other"  # Other/unknown types


class DwarfTagRegistry:
    """Centralized registry for DWARF tag mappings and categories."""

    # Canonical tag to category mapping
    TAG_TO_CATEGORY: dict[str, DwarfTagCategory] = {
        "DW_TAG_class_type": DwarfTagCategory.CLASS_LIKE,
        "DW_TAG_structure_type": DwarfTagCategory.CLASS_LIKE,
        "DW_TAG_union_type": DwarfTagCategory.CLASS_LIKE,
        "DW_TAG_typedef": DwarfTagCategory.TYPE_DEF,
        "DW_TAG_base_type": DwarfTagCategory.BASE_TYPE,
        "DW_TAG_enumeration_type": DwarfTagCategory.ENUM_TYPE,
        "DW_TAG_namespace": DwarfTagCategory.NAMESPACE,
        "DW_TAG_array_type": DwarfTagCategory.ARRAY_TYPE,
    }

    # Category to tags mapping (for reverse lookup)
    CATEGORY_TO_TAGS: dict[DwarfTagCategory, frozenset[str]] = {
        DwarfTagCategory.CLASS_LIKE: frozenset(
            ["DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"]
        ),
        DwarfTagCategory.TYPE_DEF: frozenset(["DW_TAG_typedef"]),
        DwarfTagCategory.BASE_TYPE: frozenset(["DW_TAG_base_type"]),
        DwarfTagCategory.ENUM_TYPE: frozenset(["DW_TAG_enumeration_type"]),
        DwarfTagCategory.NAMESPACE: frozenset(["DW_TAG_namespace"]),
        DwarfTagCategory.ARRAY_TYPE: frozenset(["DW_TAG_array_type"]),
    }

    # All searchable tags
    ALL_SEARCHABLE_TAGS: frozenset[str] = frozenset(
        [
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
            "DW_TAG_typedef",
            "DW_TAG_base_type",
            "DW_TAG_enumeration_type",
            "DW_TAG_namespace",
            "DW_TAG_array_type",
        ]
    )

    # Legacy type names to new tag mapping (for backward compatibility)
    LEGACY_TYPE_TO_TAGS: dict[str, frozenset[str]] = {
        "class": frozenset(["DW_TAG_class_type", "DW_TAG_structure_type"]),
        "struct": frozenset(["DW_TAG_structure_type"]),
        "union": frozenset(["DW_TAG_union_type"]),
        "typedef": frozenset(["DW_TAG_typedef"]),
        "base_type": frozenset(["DW_TAG_base_type"]),
        "enum": frozenset(["DW_TAG_enumeration_type"]),
        "namespace": frozenset(["DW_TAG_namespace"]),
        "primitive_type": frozenset(["DW_TAG_typedef", "DW_TAG_base_type"]),
    }

    @classmethod
    def get_tag_category(cls, tag: str) -> DwarfTagCategory:
        """Get category for a DWARF tag.

        Args:
            tag: DWARF tag (e.g., "DW_TAG_class_type")

        Returns:
            DwarfTagCategory enum value
        """
        return cls.TAG_TO_CATEGORY.get(tag, DwarfTagCategory.OTHER)

    @classmethod
    def get_tags_for_category(cls, category: DwarfTagCategory) -> frozenset[str]:
        """Get all tags for a category.

        Args:
            category: DwarfTagCategory enum value

        Returns:
            Frozenset of DWARF tag strings
        """
        return cls.CATEGORY_TO_TAGS.get(category, frozenset())

    @classmethod
    def get_tags_for_legacy_type(cls, legacy_type: str) -> frozenset[str]:
        """Get tags for legacy type name (for backward compatibility).

        Args:
            legacy_type: Legacy type name (e.g., "class", "typedef")

        Returns:
            Frozenset of DWARF tag strings
        """
        return cls.LEGACY_TYPE_TO_TAGS.get(legacy_type, frozenset())

    @classmethod
    def get_cache_key(cls, tag: str) -> str:
        """Get standardized cache key for a DWARF tag.

        Args:
            tag: DWARF tag (e.g., "DW_TAG_class_type")

        Returns:
            Standardized cache key (the tag itself for consistency)
        """
        return tag

    @classmethod
    def is_searchable_tag(cls, tag: str) -> bool:
        """Check if tag is searchable by the system.

        Args:
            tag: DWARF tag to check

        Returns:
            True if tag is searchable, False otherwise
        """
        return tag in cls.ALL_SEARCHABLE_TAGS

    @classmethod
    def get_human_readable_name(cls, tag: str) -> str:
        """Get human-readable name for a tag.

        Args:
            tag: DWARF tag

        Returns:
            Human-readable name
        """
        name_map = {
            "DW_TAG_class_type": "class",
            "DW_TAG_structure_type": "struct",
            "DW_TAG_union_type": "union",
            "DW_TAG_typedef": "typedef",
            "DW_TAG_base_type": "base_type",
            "DW_TAG_enumeration_type": "enum",
            "DW_TAG_namespace": "namespace",
            "DW_TAG_array_type": "array",
        }
        return name_map.get(tag, tag)

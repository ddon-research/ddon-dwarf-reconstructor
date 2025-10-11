#!/usr/bin/env python3

"""DIE type classification and validation utilities.

Provides safe tag checking and type classification for DWARF DIEs.
See docs/DWARF_TAG_ANALYSIS.md for algorithm details.

This module ensures we never make assumptions about DIE types without
checking their tags first. Critical for preventing bugs like treating
namespaces as classes or enums as forward-declarable types.
"""

from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
from ...models.dwarf.tag_constants import (
    FORWARD_DECLARABLE_TYPES,
    NAMED_TERMINAL_TYPES,
    PRIMITIVE_TYPE_NAMES,
    TYPE_QUALIFIER_TAGS,
)

logger = get_logger(__name__)


class DIETypeClassifier:
    """Classifies DIE types and validates tag usage.
    
    All methods are static as they operate on DIE objects without state.
    Use these methods instead of checking tags directly to ensure consistent
    type classification throughout the codebase.
    """

    @staticmethod
    def is_named_type(die: DIE) -> bool:
        """Check if DIE represents a named type.

        A named type has both:
        1. A tag that represents a terminal type definition
        2. A DW_AT_name attribute with the type's name

        Args:
            die: DIE to check

        Returns:
            True if DIE has a name and is a terminal type
            
        Examples:
            - DW_TAG_class_type with name "MyClass": True
            - DW_TAG_pointer_type (no name): False
            - DW_TAG_namespace with name "std": True
        """
        return die.tag in NAMED_TERMINAL_TYPES and "DW_AT_name" in die.attributes

    @staticmethod
    def is_forward_declarable(die: DIE) -> bool:
        """Check if DIE can be forward declared in C++.

        Only classes, structs, and unions can be forward declared.
        Enums, typedefs, namespaces, and base types cannot.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a class/struct/union with a name
            
        Examples:
            - DW_TAG_class_type with name: True
            - DW_TAG_enumeration_type with name: False (enums can't be forward declared)
            - DW_TAG_namespace with name: False (not a type)
        """
        return die.tag in FORWARD_DECLARABLE_TYPES and "DW_AT_name" in die.attributes

    @staticmethod
    def is_type_qualifier(die: DIE) -> bool:
        """Check if DIE is a type qualifier (pointer, const, etc.).

        Type qualifiers wrap other types and must be traversed to find
        the actual terminal type. They typically don't have DW_AT_name
        attributes - they just have DW_AT_type pointing to what they wrap.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a qualifier tag
            
        Examples:
            - DW_TAG_pointer_type: True
            - DW_TAG_const_type: True
            - DW_TAG_class_type: False
        """
        return die.tag in TYPE_QUALIFIER_TAGS

    @staticmethod
    def is_primitive_type(die: DIE) -> bool:
        """Check if DIE represents a primitive base type.

        Primitive types are built-in types (int, char, float, etc.) that
        don't need forward declarations or dependency resolution.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a base_type with primitive name
            
        Examples:
            - DW_TAG_base_type with name "int": True
            - DW_TAG_base_type with name "MyCustomInt": False
            - DW_TAG_class_type: False
        """
        if die.tag != "DW_TAG_base_type":
            return False

        name_attr = die.attributes.get("DW_AT_name")
        if not name_attr:
            return False

        # Decode name bytes to string
        if isinstance(name_attr.value, bytes):
            name = name_attr.value.decode("utf-8")
        else:
            name = str(name_attr.value)

        return name in PRIMITIVE_TYPE_NAMES

    @staticmethod
    def get_type_name(die: DIE) -> str | None:
        """Safely get type name from DIE.

        Only returns name if DIE is a named terminal type.
        Returns None for qualifiers, anonymous types, etc.

        This method ensures we only extract names from appropriate DIEs.

        Args:
            die: DIE to get name from

        Returns:
            Type name if available, None otherwise
            
        Examples:
            - DW_TAG_class_type with name "MyClass": "MyClass"
            - DW_TAG_pointer_type (no name): None
            - DW_TAG_member with name "field": None (not a type)
        """
        if not DIETypeClassifier.is_named_type(die):
            return None

        name_attr = die.attributes.get("DW_AT_name")
        if not name_attr:
            return None

        # Decode name bytes to string
        if isinstance(name_attr.value, bytes):
            return name_attr.value.decode("utf-8")
        return str(name_attr.value)

    @staticmethod
    def requires_resolution(die: DIE) -> bool:
        """Check if DIE represents a type that needs dependency resolution.
        
        Types that need resolution are:
        - Classes, structs, unions (forward declarable)
        - Non-primitive types
        
        Types that DON'T need resolution:
        - Primitives (int, char, etc.)
        - Enums (just values)
        - Typedefs (aliases)
        - Qualifiers (transparent wrappers)
        
        Args:
            die: DIE to check
            
        Returns:
            True if type should be included in dependencies
        """
        # Must be forward declarable (class/struct/union with name)
        if not DIETypeClassifier.is_forward_declarable(die):
            return False

        # Must not be a primitive
        return not DIETypeClassifier.is_primitive_type(die)

#!/usr/bin/env python3

"""DWARF tag constants and type classification.

Defines tag categories based on DWARF standard and project's actual tag usage.
See docs/DWARF_TAG_ANALYSIS.md for detailed analysis.

These constants are used to properly classify DIE types and determine how to
handle them during type resolution and dependency extraction.
"""

# Terminal types that have names and represent actual type definitions
# These are the types we want to find and store as dependencies
NAMED_TERMINAL_TYPES = frozenset(
    {
        "DW_TAG_class_type",  # C++ classes
        "DW_TAG_structure_type",  # C structs
        "DW_TAG_union_type",  # Unions
        "DW_TAG_enumeration_type",  # Enums
        "DW_TAG_base_type",  # Primitives (int, char, etc.)
        "DW_TAG_namespace",  # Namespaces (for scope)
    }
)

# Types that can be forward declared in C++ headers
# Only class, struct, and union can be forward declared
# Enums, typedefs, and namespaces cannot be forward declared
FORWARD_DECLARABLE_TYPES = frozenset(
    {
        "DW_TAG_class_type",
        "DW_TAG_structure_type",
        "DW_TAG_union_type",
    }
)

# Type qualifiers that wrap other types (must traverse through)
# These tags don't have names themselves - they modify other types
# We must follow DW_AT_type references through these to find the terminal type
TYPE_QUALIFIER_TAGS = frozenset(
    {
        "DW_TAG_pointer_type",  # *
        "DW_TAG_reference_type",  # &
        "DW_TAG_rvalue_reference_type",  # &&
        "DW_TAG_const_type",  # const
        "DW_TAG_volatile_type",  # volatile
        "DW_TAG_restrict_type",  # restrict
    }
)

# Primitive type names (don't need resolution)
# These are built-in types that don't need forward declarations
PRIMITIVE_TYPE_NAMES = frozenset(
    {
        # Basic C types
        "void",
        "bool",
        "char",
        "signed char",
        "unsigned char",
        "short",
        "unsigned short",
        "int",
        "unsigned int",
        "long",
        "unsigned long",
        "long long",
        "unsigned long long",
        "float",
        "double",
        "long double",
        # C++ character types
        "wchar_t",
        "char16_t",
        "char32_t",
        # Platform-specific types
        "size_t",
        "ptrdiff_t",
        "intptr_t",
        "uintptr_t",
        # Fixed-width integer types (stdint.h)
        "int8_t",
        "uint8_t",
        "int16_t",
        "uint16_t",
        "int32_t",
        "uint32_t",
        "int64_t",
        "uint64_t",
        # Platform-specific variants (common in DWARF)
        "__int8_t",
        "__uint8_t",
        "__int16_t",
        "__uint16_t",
        "__int32_t",
        "__uint32_t",
        "__int64_t",
        "__uint64_t",
        # Fast/least variants
        "int_fast8_t",
        "uint_fast8_t",
        "int_fast16_t",
        "uint_fast16_t",
        "int_fast32_t",
        "uint_fast32_t",
        "int_fast64_t",
        "uint_fast64_t",
        "int_least8_t",
        "uint_least8_t",
        "int_least16_t",
        "uint_least16_t",
        "int_least32_t",
        "uint_least32_t",
        "int_least64_t",
        "uint_least64_t",
    }
)

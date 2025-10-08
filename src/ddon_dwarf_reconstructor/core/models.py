"""DWARF constants and enums for reference."""

from enum import Enum


class DWAccessibility(Enum):
    """DWARF accessibility attribute values."""

    PUBLIC = "DW_ACCESS_public"
    PRIVATE = "DW_ACCESS_private"
    PROTECTED = "DW_ACCESS_protected"


class DWVirtuality(Enum):
    """DWARF virtuality attribute values."""

    NONE = "DW_VIRTUALITY_none"
    VIRTUAL = "DW_VIRTUALITY_virtual"
    PURE_VIRTUAL = "DW_VIRTUALITY_pure_virtual"


class DWTag(Enum):
    """Common DWARF tag types."""

    CLASS_TYPE = "DW_TAG_class_type"
    STRUCTURE_TYPE = "DW_TAG_structure_type"
    UNION_TYPE = "DW_TAG_union_type"
    MEMBER = "DW_TAG_member"
    INHERITANCE = "DW_TAG_inheritance"
    SUBPROGRAM = "DW_TAG_subprogram"
    FORMAL_PARAMETER = "DW_TAG_formal_parameter"
    TYPEDEF = "DW_TAG_typedef"
    POINTER_TYPE = "DW_TAG_pointer_type"
    REFERENCE_TYPE = "DW_TAG_reference_type"
    CONST_TYPE = "DW_TAG_const_type"
    VOLATILE_TYPE = "DW_TAG_volatile_type"
    BASE_TYPE = "DW_TAG_base_type"
    ARRAY_TYPE = "DW_TAG_array_type"
    ENUMERATION_TYPE = "DW_TAG_enumeration_type"
    ENUMERATOR = "DW_TAG_enumerator"
    VARIABLE = "DW_TAG_variable"

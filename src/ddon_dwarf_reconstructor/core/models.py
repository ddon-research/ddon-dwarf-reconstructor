"""Type abstractions for DWARF debug information entities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


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


@dataclass
class DIEReference:
    """Represents a reference to another Debug Information Entry."""

    offset: int
    global_offset: Optional[int] = None
    name: Optional[str] = None

    def __str__(self) -> str:
        """String representation of the reference."""
        if self.name:
            return f"<0x{self.offset:08x}> -> {self.name}"
        return f"<0x{self.offset:08x}>"


@dataclass
class DWARFAttribute:
    """Represents a single DWARF attribute."""

    name: str
    value: Any
    raw_value: Optional[str] = None

    def __str__(self) -> str:
        """String representation of the attribute."""
        return f"{self.name}: {self.value}"


@dataclass
class DIE:
    """Debug Information Entry - represents a single DWARF DIE."""

    level: int
    offset: int
    global_offset: int
    tag: str
    attributes: dict[str, DWARFAttribute] = field(default_factory=dict)
    children: list["DIE"] = field(default_factory=list)
    parent: Optional["DIE"] = None

    def get_attribute(self, attr_name: str) -> Optional[DWARFAttribute]:
        """Get an attribute by name."""
        return self.attributes.get(attr_name)

    def get_name(self) -> Optional[str]:
        """Get the DW_AT_name attribute value if it exists."""
        attr = self.get_attribute("DW_AT_name")
        return attr.value if attr else None

    def get_byte_size(self) -> Optional[int]:
        """Get the DW_AT_byte_size attribute value if it exists."""
        attr = self.get_attribute("DW_AT_byte_size")
        return int(attr.value) if attr else None

    def get_type_ref(self) -> Optional[DIEReference]:
        """Get the DW_AT_type reference if it exists."""
        attr = self.get_attribute("DW_AT_type")
        if attr and isinstance(attr.value, DIEReference):
            return attr.value
        return None

    def is_class(self) -> bool:
        """Check if this DIE represents a class type."""
        return self.tag == DWTag.CLASS_TYPE.value

    def is_struct(self) -> bool:
        """Check if this DIE represents a struct type."""
        return self.tag == DWTag.STRUCTURE_TYPE.value

    def is_member(self) -> bool:
        """Check if this DIE represents a member variable."""
        return self.tag == DWTag.MEMBER.value

    def is_subprogram(self) -> bool:
        """Check if this DIE represents a subprogram (method/function)."""
        return self.tag == DWTag.SUBPROGRAM.value

    def __str__(self) -> str:
        """String representation of the DIE."""
        name = self.get_name()
        if name:
            return f"<{self.level}><0x{self.offset:08x}> {self.tag}: {name}"
        return f"<{self.level}><0x{self.offset:08x}> {self.tag}"


@dataclass
class CompilationUnit:
    """Represents a DWARF compilation unit."""

    offset: int
    size: int
    version: int
    address_size: int
    dies: list[DIE] = field(default_factory=list)

    def find_dies_by_name(self, name: str) -> list[DIE]:
        """Find all DIEs with a specific name."""
        results: list[DIE] = []
        for die in self.dies:
            if die.get_name() == name:
                results.append(die)
        return results

    def find_dies_by_tag(self, tag: str) -> list[DIE]:
        """Find all DIEs with a specific tag."""
        results: list[DIE] = []
        for die in self.dies:
            if die.tag == tag:
                results.append(die)
        return results
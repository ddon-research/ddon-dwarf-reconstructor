"""Aggregate parsing operations for the class-parser façade."""

from __future__ import annotations

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger
from ...models.dwarf import (
    EnumeratorInfo,
    EnumInfo,
    StructInfo,
    UnionInfo,
)
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)


class ClassParserAggregateTypesMixin:
    def parse_enum(self: ClassParserContext, enum_die: DwarfEntry) -> EnumInfo | None:
        """Parse an enumeration using pyelftools.

        Args:
            enum_die: DwarfEntry representing the enum

        Returns:
            EnumInfo object if valid, None otherwise
        """
        # Get enum name
        name_attr = enum_die.attributes.get("DW_AT_name")
        enum_name = name_attr.value.decode("utf-8") if name_attr else "unknown_enum"

        # Get enum size
        size_attr = enum_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr else 4

        # Parse enumerators
        enumerators = []
        for child in enum_die.iter_children():
            if child.tag == "DW_TAG_enumerator":
                enumerator = self._parse_enumerator(child)
                if enumerator:
                    enumerators.append(enumerator)

        return EnumInfo(
            name=enum_name,
            byte_size=byte_size,
            enumerators=enumerators,
        )

    def _parse_enumerator(
        self: ClassParserContext, enumerator_die: DwarfEntry
    ) -> EnumeratorInfo | None:
        """Parse an enumerator value."""
        name_attr = enumerator_die.attributes.get("DW_AT_name")
        if not name_attr:
            return None
        enumerator_name = name_attr.value.decode("utf-8")

        value_attr = enumerator_die.attributes.get("DW_AT_const_value")
        if not value_attr:
            return None

        value = value_attr.value
        if isinstance(value, bytes):
            value = int.from_bytes(value, byteorder="little", signed=True) if len(value) <= 8 else 0
        elif not isinstance(value, int):
            try:
                value = int(value)
            except ValueError, TypeError:
                value = 0

        return EnumeratorInfo(name=enumerator_name, value=value)

    def parse_nested_structure(
        self: ClassParserContext, struct_die: DwarfEntry
    ) -> StructInfo | None:
        """Parse a nested structure definition.

        Args:
            struct_die: DwarfEntry representing the struct

        Returns:
            StructInfo object if valid, None otherwise
        """
        # Get structure name (can be None for anonymous structs)
        name_attr = struct_die.attributes.get("DW_AT_name")
        struct_name = None
        if name_attr:
            struct_name = (
                name_attr.value.decode("utf-8")
                if isinstance(name_attr.value, bytes)
                else str(name_attr.value)
            )

        # Get structure size
        size_attr = struct_die.attributes.get("DW_AT_byte_size")
        struct_size = size_attr.value if size_attr else 0

        # Parse members
        members = []
        for child in struct_die.iter_children():
            if child.tag == "DW_TAG_member":
                member = self.parse_member(child)
                if member:
                    members.append(member)

        return StructInfo(
            name=struct_name,
            byte_size=struct_size,
            members=members,
            die_offset=struct_die.offset,
        )

    def parse_union(self: ClassParserContext, union_die: DwarfEntry) -> UnionInfo | None:
        """Parse a union definition.

        Args:
            union_die: DwarfEntry representing the union

        Returns:
            UnionInfo object if valid, None otherwise
        """
        # Get union name (might be None for anonymous unions)
        name_attr = union_die.attributes.get("DW_AT_name")
        union_name = name_attr.value.decode("utf-8") if name_attr else ""

        # Get union size
        size_attr = union_die.attributes.get("DW_AT_byte_size")
        union_size = size_attr.value if size_attr else 0

        # Parse members and nested structs
        members = []
        nested_structs = []

        for child in union_die.iter_children():
            if child.tag == "DW_TAG_member":
                member = self.parse_member(child)
                if member:
                    members.append(member)

            elif child.tag == "DW_TAG_structure_type":
                # Handle anonymous structs within unions
                struct_info = self.parse_nested_structure(child)
                if struct_info:
                    nested_structs.append(struct_info)

        return UnionInfo(
            name=union_name,
            byte_size=union_size,
            members=members,
            nested_structs=nested_structs,
            die_offset=union_die.offset,
        )

    def _get_declaration_file(
        self: ClassParserContext, cu: DwarfCompilationUnit, die: DwarfEntry
    ) -> str | None:
        """Get declaration file name from line program."""
        decl_file_attr = die.attributes.get("DW_AT_decl_file")
        if not decl_file_attr:
            return None

        try:
            line_program = self.dwarf_info.line_program_for_CU(cu)
            file_index = decl_file_attr.value
            if line_program and 0 < file_index <= len(line_program.header.file_entry):
                file_entry = line_program.header.file_entry[decl_file_attr.value - 1]
                return (
                    file_entry.name.decode("utf-8")
                    if hasattr(file_entry.name, "decode")
                    else str(file_entry.name)
                )
        except Exception:
            pass

        return None

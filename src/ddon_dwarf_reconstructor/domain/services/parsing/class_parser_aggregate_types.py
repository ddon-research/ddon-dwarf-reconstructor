"""Aggregate parsing operations for the class-parser façade."""

from __future__ import annotations

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, decode_dwarf_string
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
        enum_name = (
            decode_dwarf_string(name_attr.value) if name_attr is not None else "unknown_enum"
        )

        # Get enum size
        size_attr = enum_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr is not None else 4

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
        if name_attr is None:
            return None
        enumerator_name = decode_dwarf_string(name_attr.value)

        value_attr = enumerator_die.attributes.get("DW_AT_const_value")
        if value_attr is None:
            return None

        value = self._enumerator_value(value_attr.value)
        if value is None:
            logger.warning("Ignoring invalid value for enumerator %s", enumerator_name)
            return None

        return EnumeratorInfo(name=enumerator_name, value=value)

    @staticmethod
    def _enumerator_value(raw_value: object) -> int | None:
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, bytes):
            if not 0 < len(raw_value) <= 8:
                return None
            return int.from_bytes(raw_value, byteorder="little", signed=True)
        if isinstance(raw_value, str):
            try:
                return int(raw_value, 0)
            except ValueError, TypeError:
                return None
        return None

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
        if name_attr is not None:
            struct_name = decode_dwarf_string(name_attr.value)

        # Get structure size
        size_attr = struct_die.attributes.get("DW_AT_byte_size")
        struct_size = size_attr.value if size_attr is not None else 0

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
        union_name = decode_dwarf_string(name_attr.value) if name_attr is not None else ""

        # Get union size
        size_attr = union_die.attributes.get("DW_AT_byte_size")
        union_size = size_attr.value if size_attr is not None else 0

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
        if decl_file_attr is None:
            return None

        try:
            line_program = self.dwarf_info.line_program_for_CU(cu)
            file_index = decl_file_attr.value
            if line_program is not None and 0 < file_index <= len(line_program.header.file_entry):
                file_entry = line_program.header.file_entry[decl_file_attr.value - 1]
                return decode_dwarf_string(file_entry.name)
        except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.debug("Unable to resolve declaration file for CU %s: %s", cu.cu_offset, error)
            pass

        return None

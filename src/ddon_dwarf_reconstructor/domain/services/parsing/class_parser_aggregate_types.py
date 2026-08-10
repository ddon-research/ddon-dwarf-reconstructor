"""Aggregate parsing operations for the class-parser façade."""

from __future__ import annotations

import logging
from decimal import Decimal
from numbers import Integral

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger, log_event
from ...models.dwarf import (
    EnumeratorInfo,
    EnumInfo,
    StructInfo,
    UnionInfo,
)
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)
_SIGNED_ENCODINGS = frozenset({0x05, 0x06})
_UNSIGNED_ENCODINGS = frozenset({0x07, 0x08})


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
        byte_size = self._exact_integer(size_attr.value) if size_attr is not None else None
        if byte_size is None or byte_size <= 0:
            byte_size = 4
        signed = self._enum_signedness(enum_die)

        # Parse enumerators
        enumerators = []
        for child in enum_die.iter_children():
            if child.tag == "DW_TAG_enumerator":
                enumerator = self._parse_enumerator(
                    child,
                    enum_die=enum_die,
                    enum_byte_size=byte_size,
                    signed=signed,
                )
                if enumerator:
                    enumerators.append(enumerator)

        return EnumInfo(
            name=enum_name,
            byte_size=byte_size,
            enumerators=enumerators,
        )

    def _parse_enumerator(
        self: ClassParserContext,
        enumerator_die: DwarfEntry,
        *,
        enum_die: DwarfEntry | None = None,
        enum_byte_size: int | None = None,
        signed: bool | None = None,
    ) -> EnumeratorInfo | None:
        """Parse an enumerator value."""
        name_attr = enumerator_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        enumerator_name = decode_dwarf_string(name_attr.value)

        value_attr = enumerator_die.attributes.get("DW_AT_const_value")
        if value_attr is None:
            return None

        value = self._enumerator_value(
            value_attr.value,
            form=getattr(value_attr, "form", ""),
            byte_size=enum_byte_size,
            signed=signed,
        )
        if value is None:
            log_event(
                logger,
                logging.WARNING,
                "invalid_enum_value",
                enumerator=enumerator_name,
                enum_offset=getattr(enum_die, "offset", None),
                die_offset=getattr(enumerator_die, "offset", None),
                form=str(getattr(value_attr, "form", "")),
                raw_type=type(value_attr.value).__name__,
                raw_size=(
                    len(value_attr.value)
                    if isinstance(value_attr.value, (bytes, bytearray, memoryview))
                    else None
                ),
                enum_byte_size=enum_byte_size,
                signed=signed,
                reason="unsupported_or_out_of_range",
            )
            return None

        return EnumeratorInfo(name=enumerator_name, value=value)

    @staticmethod
    def _enumerator_value(
        raw_value: object,
        *,
        form: str = "",
        byte_size: int | None = None,
        signed: bool | None = None,
    ) -> int | None:
        if isinstance(raw_value, bool):
            return None
        effective_signed = signed if signed is not None else form != "DW_FORM_udata"

        value = ClassParserAggregateTypesMixin._coerce_enum_value(
            raw_value, byte_size, effective_signed
        )
        if value is None:
            return None

        if byte_size is not None and not ClassParserAggregateTypesMixin._fits_enum_width(
            value, byte_size, effective_signed
        ):
            return None
        return value

    @staticmethod
    def _coerce_enum_value(raw_value: object, byte_size: int | None, signed: bool) -> int | None:
        if isinstance(raw_value, (bytes, bytearray, memoryview)):
            raw_bytes = bytes(raw_value)
            if not 0 < len(raw_bytes) <= 8:
                return None
            if byte_size is not None and len(raw_bytes) > byte_size:
                return None
            return int.from_bytes(raw_bytes, byteorder="little", signed=signed)
        if isinstance(raw_value, str):
            return ClassParserAggregateTypesMixin._parse_integer_text(raw_value)
        return ClassParserAggregateTypesMixin._exact_integer(raw_value)

    @staticmethod
    def _exact_integer(raw_value: object) -> int | None:
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, Integral):
            return int(raw_value)
        if (
            isinstance(raw_value, Decimal)
            and raw_value.is_finite()
            and raw_value == raw_value.to_integral_value()
        ):
            return int(raw_value)
        return None

    @staticmethod
    def _parse_integer_text(raw_value: str) -> int | None:
        text = raw_value.strip()
        if not text:
            return None
        try:
            return int(text, 0)
        except ValueError, TypeError:
            try:
                return int(text, 10)
            except ValueError, TypeError:
                return None

    @staticmethod
    def _fits_enum_width(value: int, byte_size: int, signed: bool) -> bool:
        if byte_size <= 0:
            return True
        bit_count = byte_size * 8
        if signed:
            return -(1 << (bit_count - 1)) <= value <= (1 << (bit_count - 1)) - 1
        return 0 <= value <= (1 << bit_count) - 1

    @classmethod
    def _enum_signedness(cls, enum_die: DwarfEntry) -> bool | None:
        if enum_die.attributes.get("DW_AT_type") is None:
            return None
        try:
            type_die = enum_die.get_DIE_from_attribute("DW_AT_type")
        except AttributeError, KeyError, RuntimeError, TypeError, ValueError:
            return None
        if type_die is None:
            return None
        encoding_attr = type_die.attributes.get("DW_AT_encoding")
        if encoding_attr is None:
            return None
        encoding = cls._exact_integer(encoding_attr.value)
        if encoding in _SIGNED_ENCODINGS:
            return True
        if encoding in _UNSIGNED_ENCODINGS:
            return False
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
            logger.debug(
                "Unable to resolve declaration file for CU %s: %s",
                cu.cu_offset,
                error,
                exc_info=error,
            )

        return None

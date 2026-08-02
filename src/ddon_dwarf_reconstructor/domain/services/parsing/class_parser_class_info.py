"""Aggregate parsing operations for the class-parser façade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger, log_timing
from ...models.dwarf import (
    ClassInfo,
    MemberInfo,
    UnionInfo,
)
from .class_parser_children import ClassParserChildrenMixin
from .class_parser_context import ClassParserContext
from .dwarf_location_parser import parse_location_offset
from .parser_policy import DWARF_ACCESS_NAMES
from .type_chain_traverser import TypeChainTraverser

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ClassParserClassInfoMixin(ClassParserChildrenMixin):
    @log_timing
    def parse_class_info(self: ClassParserContext, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Parse a class DIE into a stable domain model."""
        header = self._class_header(cu, class_die)
        children = self._parse_class_children(cu, class_die, header[0])
        return ClassInfo(
            name=header[0],
            byte_size=header[1],
            members=children.members,
            methods=children.methods,
            base_classes=children.base_classes,
            enums=children.enums,
            nested_structs=children.nested_structs,
            unions=children.unions,
            nested_classes=children.nested_classes,
            alignment=header[2],
            declaration_file=header[3],
            declaration_line=header[4],
            die_offset=header[5],
            cu_offset=cu.cu_offset,
            packing_info=None,
            template_type_params=children.template_type_params,
            template_value_params=children.template_value_params,
            kind=header[6],
            qualified_name=header[7],
            is_declaration=header[8],
            containing_type=header[9],
        )

    def _class_header(
        self: ClassParserContext, cu: CompileUnit, class_die: DIE
    ) -> tuple[str, int, int | None, str | None, int | None, int, str, str, bool, str | None]:
        name_attr = class_die.attributes.get("DW_AT_name")
        class_name = name_attr.value.decode("utf-8") if name_attr else "unknown_class"
        aggregate_kind = {
            "DW_TAG_class_type": "class",
            "DW_TAG_structure_type": "struct",
            "DW_TAG_union_type": "union",
        }.get(class_die.tag if isinstance(class_die.tag, str) else "", "class")
        qualified_name = self._get_qualified_name(class_die, class_name)
        logger.debug("Parsing class: %s", class_name)
        size_attr = class_die.attributes.get("DW_AT_byte_size")
        alignment_attr = class_die.attributes.get("DW_AT_alignment")
        decl_line_attr = class_die.attributes.get("DW_AT_decl_line")
        return (
            class_name,
            size_attr.value if size_attr else 0,
            alignment_attr.value if alignment_attr else None,
            self._get_declaration_file(cu, class_die),
            decl_line_attr.value if decl_line_attr else None,
            class_die.offset,
            aggregate_kind,
            qualified_name,
            "DW_AT_declaration" in class_die.attributes,
            self._get_containing_type(class_die),
        )

    def _get_qualified_name(self: ClassParserContext, die: DIE, name: str) -> str:
        """Build a qualified name from namespace and containing-type parents."""
        components = [name]
        current_die = die
        while True:
            try:
                parent_die = current_die.get_parent()
            except AttributeError, RuntimeError:
                break
            if parent_die is None or parent_die.tag not in {
                "DW_TAG_namespace",
                "DW_TAG_class_type",
                "DW_TAG_structure_type",
                "DW_TAG_union_type",
            }:
                break
            parent_name = parent_die.attributes.get("DW_AT_name")
            if parent_name is None:
                break
            parent_value = parent_name.value
            components.append(
                parent_value.decode("utf-8", errors="replace")
                if isinstance(parent_value, bytes)
                else str(parent_value)
            )
            current_die = parent_die
        return "::".join(reversed(components))

    def _get_containing_type(self: ClassParserContext, die: DIE) -> str | None:
        """Return the qualified aggregate containing ``die``, when present."""
        try:
            parent_die = die.get_parent()
        except AttributeError, RuntimeError:
            return None

        if parent_die is None or parent_die.tag not in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }:
            return None

        name_attr = parent_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        parent_name = (
            name_attr.value.decode("utf-8", errors="replace")
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )
        return self._get_qualified_name(parent_die, parent_name)

    @staticmethod
    def _get_accessibility(die: DIE) -> str:
        """Return the C++ access level represented by a DWARF attribute."""
        attribute = die.attributes.get("DW_AT_accessibility")
        if attribute is None:
            return "public"
        value = getattr(attribute, "value", 1)
        return DWARF_ACCESS_NAMES.get(value, "public")

    def _parse_member_or_anonymous(
        self: ClassParserContext,
        member_die: DIE,
        class_name: str,
        processed_offsets: set[int],
    ) -> MemberInfo | UnionInfo | None:
        """Parse member, detecting and handling anonymous unions.

        Args:
            member_die: DIE representing the member
            class_name: Name of containing class (for logging)
            processed_offsets: Set of already-processed union offsets

        Returns:
            MemberInfo for regular members, UnionInfo for anonymous unions, None to skip
        """
        name_attr = member_die.attributes.get("DW_AT_name")
        type_attr = member_die.attributes.get("DW_AT_type")

        # Check for anonymous union/struct
        if not name_attr and type_attr:
            try:
                type_die = member_die.get_DIE_from_attribute("DW_AT_type")
                if type_die and type_die.tag == "DW_TAG_union_type":
                    # Anonymous union
                    union_info = self.parse_union(type_die)
                    if union_info:
                        processed_offsets.add(type_die.offset)
                        logger.debug(
                            f"Found anonymous union in {class_name}: "
                            f"({union_info.byte_size} bytes)",
                        )
                        return union_info
            except Exception as e:
                logger.debug(f"Failed to resolve anonymous member type: {e}")

        # Regular member
        return self.parse_member(member_die)

    def parse_member(self: ClassParserContext, member_die: DIE) -> MemberInfo | None:
        """Parse a class member using pyelftools.

        Args:
            member_die: DIE representing the member

        Returns:
            MemberInfo object if valid, None otherwise
        """
        # Resolve member type first (for display)
        type_name = self.type_resolver.resolve_type_name(member_die)

        type_offset = TypeChainTraverser.get_terminal_type_offset(member_die)
        if type_offset is not None:
            logger.debug(f"Captured type offset 0x{type_offset:x} for member type '{type_name}'")

        member_name = self._member_name(member_die, type_name)
        if member_name is None:
            return None

        layout = self._member_layout(member_die)
        type_name = self._vtable_type(member_name, type_name)

        return MemberInfo(
            name=member_name,
            type_name=type_name,
            type_offset=type_offset,  # NEW: Store terminal type offset
            offset=layout[0],
            is_static=layout[1],
            is_const=layout[2] is not None,
            const_value=layout[2],
            access=self._get_accessibility(member_die),
            is_volatile=type_name.startswith("volatile "),
            bit_size=layout[3],
            bit_offset=layout[4],
        )

    @staticmethod
    def _member_name(member_die: DIE, type_name: str) -> str | None:
        name_attr = member_die.attributes.get("DW_AT_name")
        if name_attr is not None:
            value = name_attr.value
            return value.decode("utf-8") if isinstance(value, bytes) else str(value)
        if "union_type" in type_name or "structure_type" in type_name:
            logger.debug("Skipping unnamed union/struct member: %s", type_name)
            return None
        if "union" in type_name.lower() or "struct" in type_name.lower():
            return ""
        return None

    @staticmethod
    def _member_layout(
        member_die: DIE,
    ) -> tuple[int | None, bool, int | None, int | None, int | None]:
        is_static = (
            member_die.attributes.get("DW_AT_external") is not None
            and member_die.attributes.get("DW_AT_declaration") is not None
        )
        const_attr = member_die.attributes.get("DW_AT_const_value")
        offset_attr = member_die.attributes.get("DW_AT_data_member_location")
        bit_size_attr = member_die.attributes.get("DW_AT_bit_size")
        bit_offset_attr = member_die.attributes.get(
            "DW_AT_data_bit_offset"
        ) or member_die.attributes.get("DW_AT_bit_offset")
        const_value = (
            const_attr.value
            if const_attr is not None and isinstance(const_attr.value, int)
            else None
        )
        return (
            parse_location_offset(offset_attr.value) if offset_attr else None,
            is_static,
            const_value,
            bit_size_attr.value if bit_size_attr else None,
            bit_offset_attr.value if bit_offset_attr else None,
        )

    @staticmethod
    def _vtable_type(member_name: str, type_name: str) -> str:
        if member_name.startswith("_vptr$") and (
            type_name == "unknown_type" or "__vtbl_ptr_type" in type_name
        ):
            logger.info("Applying vtable pointer fallback for %s", member_name)
            return "void*"
        return type_name

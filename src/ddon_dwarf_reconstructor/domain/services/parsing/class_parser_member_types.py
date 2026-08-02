"""Member-type recovery operations for the class-parser façade."""

from __future__ import annotations

from collections.abc import Mapping

from ....core.dwarf import DwarfEntry
from ...models.dwarf import StructInfo
from .class_parser_context import ClassParserContext


class ClassParserMemberTypesMixin:
    """Recover inline aggregates and safe storage fallbacks for members."""

    @staticmethod
    def _member_type_die(member_die: DwarfEntry) -> DwarfEntry | None:
        if "DW_AT_type" not in member_die.attributes:
            return None
        return member_die.get_DIE_from_attribute("DW_AT_type")

    def _inline_struct_type(
        self: ClassParserContext, type_die: DwarfEntry | None
    ) -> StructInfo | None:
        if type_die is None or type_die.tag not in {"DW_TAG_class_type", "DW_TAG_structure_type"}:
            return None
        if "DW_AT_name" in type_die.attributes:
            return None
        return self.parse_nested_structure(type_die)

    @staticmethod
    def _opaque_storage_size(member_die: DwarfEntry, type_die: DwarfEntry | None) -> int | None:
        """Use byte storage when flattening would make an alternate type recursive."""
        aggregate = ClassParserMemberTypesMixin._named_aggregate(type_die)
        if aggregate is None:
            return None
        try:
            parent = member_die.get_parent()
        except AttributeError, RuntimeError:
            return None
        if not ClassParserMemberTypesMixin._has_same_name(parent, aggregate):
            return None
        size_attr = aggregate.attributes.get("DW_AT_byte_size")
        if size_attr is None or not isinstance(size_attr.value, int):
            return None
        return size_attr.value

    @staticmethod
    def _named_aggregate(type_die: DwarfEntry | None) -> DwarfEntry | None:
        if type_die is None or type_die.tag not in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }:
            return None
        return type_die if "DW_AT_name" in type_die.attributes else None

    @staticmethod
    def _has_same_name(parent: object, type_die: DwarfEntry) -> bool:
        if not isinstance(getattr(parent, "tag", None), str):
            return False
        attributes = getattr(parent, "attributes", None)
        if not isinstance(attributes, Mapping):
            return False
        parent_name = attributes.get("DW_AT_name")
        type_name = type_die.attributes.get("DW_AT_name")
        if parent_name is None or type_name is None:
            return False
        if parent_name.value != type_name.value:
            return False
        return getattr(parent, "offset", None) != type_die.offset

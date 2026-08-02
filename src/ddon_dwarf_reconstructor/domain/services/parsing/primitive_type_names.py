"""Names and declarator syntax recovered from primitive DIE chains."""

from __future__ import annotations

from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)


class PrimitiveTypeNamesMixin:
    def _get_primitive_base_type_name(self: TypeResolverContext, type_die: DIE) -> str:
        """Return a display name while preserving pointer and qualifier syntax."""
        tag = type_die.tag
        if tag in {"DW_TAG_base_type", "DW_TAG_typedef"}:
            return self._named_or_typedef_name(type_die)
        if tag in {
            "DW_TAG_pointer_type",
            "DW_TAG_reference_type",
            "DW_TAG_const_type",
            "DW_TAG_volatile_type",
        }:
            return self._qualified_primitive_name(type_die)
        if tag in {
            "DW_TAG_ptr_to_member_type",
            "DW_TAG_subroutine_type",
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }:
            return self._special_primitive_name(type_die)
        logger.debug("Unhandled type DIE tag: %s", tag)
        return "unknown_type"

    def _named_or_typedef_name(self: TypeResolverContext, type_die: DIE) -> str:
        if type_die.tag == "DW_TAG_base_type":
            return self._die_name(type_die) or "unknown_type"
        return self._resolve_referenced_name(type_die, "unknown_type")

    def _qualified_primitive_name(self: TypeResolverContext, type_die: DIE) -> str:
        if type_die.tag == "DW_TAG_pointer_type":
            return self._resolve_referenced_name(type_die, "void", "*")
        if type_die.tag == "DW_TAG_reference_type":
            return self._resolve_referenced_name(type_die, "void", "&")
        qualifier = "const" if type_die.tag == "DW_TAG_const_type" else "volatile"
        referenced_name = self._resolve_referenced_name(type_die, "unknown_type")
        return f"{qualifier} {referenced_name}"

    def _special_primitive_name(self: TypeResolverContext, type_die: DIE) -> str:
        if type_die.tag == "DW_TAG_ptr_to_member_type":
            return self._resolve_member_pointer_name(type_die)
        if type_die.tag == "DW_TAG_subroutine_type":
            return self._resolve_subroutine_name(type_die)
        return self._die_name(type_die) or "unknown_type"

    def _resolve_referenced_name(
        self: TypeResolverContext,
        type_die: DIE,
        missing_name: str,
        suffix: str = "",
    ) -> str:
        if "DW_AT_type" not in type_die.attributes:
            return missing_name
        target_die = type_die.get_DIE_from_attribute("DW_AT_type")
        if target_die is None:
            return missing_name
        return f"{self._get_primitive_base_type_name(target_die)}{suffix}"

    def _resolve_member_pointer_name(self: TypeResolverContext, type_die: DIE) -> str:
        for attribute_name in ("DW_AT_containing_type", "DW_AT_type"):
            if attribute_name not in type_die.attributes:
                continue
            target_die = type_die.get_DIE_from_attribute(attribute_name)
            if target_die:
                return self._get_primitive_base_type_name(target_die)
        logger.debug("Incomplete pointer-to-member type at offset 0x%x", type_die.offset)
        return "unknown_type"

    def _resolve_subroutine_name(self: TypeResolverContext, type_die: DIE) -> str:
        if "DW_AT_type" not in type_die.attributes:
            return "void"
        target_die = type_die.get_DIE_from_attribute("DW_AT_type")
        return self._get_primitive_base_type_name(target_die) if target_die else "void"

    @staticmethod
    def _die_name(type_die: DIE) -> str | None:
        name_attr = type_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        value = name_attr.value
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    def _extract_base_type(self: TypeResolverContext, type_name: str) -> str:
        """Remove qualifiers, array dimensions, and indirection from a type name."""
        original_name = type_name
        type_name = self._strip_type_qualifiers(type_name)
        type_name = self._strip_array_suffix(type_name)
        type_name = self._strip_indirection(type_name)
        logger.debug("Type extraction: '%s' -> '%s'", original_name, type_name)
        return type_name

    @staticmethod
    def _strip_type_qualifiers(type_name: str) -> str:
        while type_name.startswith(("const ", "volatile ")):
            prefix_length = 6 if type_name.startswith("const ") else 9
            type_name = type_name[prefix_length:].strip()
        return type_name

    @staticmethod
    def _strip_array_suffix(type_name: str) -> str:
        return (
            type_name.split("[", 1)[0].strip()
            if "[" in type_name and "]" in type_name
            else type_name
        )

    @staticmethod
    def _strip_indirection(type_name: str) -> str:
        while type_name.endswith(("&&", "&", "*")):
            type_name = type_name[: -(2 if type_name.endswith("&&") else 1)].strip()
        return type_name

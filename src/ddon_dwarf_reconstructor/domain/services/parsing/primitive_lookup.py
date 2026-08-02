"""Lazy lookup of typedefs and primitive base types."""

from __future__ import annotations

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger
from ..search_result import SearchStatus
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)

_EXCLUDED_TYPES = frozenset(
    {
        "void",
        "int",
        "char",
        "float",
        "double",
        "bool",
        "unsigned",
        "signed",
        "short",
        "long",
        "unknown_type",
        "class_type",
        "structure_type",
        "union_type",
        "subroutine_type",
    }
)


class PrimitiveLookupMixin:
    def _resolve_primitive_typedef(self: TypeResolverContext, typedef_name: str) -> str | None:
        """Resolve a primitive or typedef through the offset index."""
        if not self.index:
            logger.debug("No index available for type resolution: %s", typedef_name)
            return None
        search_name = typedef_name.rstrip("*&").strip()
        if search_name in _EXCLUDED_TYPES:
            return search_name
        offset = self._lookup_primitive_offset(search_name)
        if offset is None:
            logger.debug("No offset found for typedef: %s", search_name)
            return None
        die = self.index.get_die_by_offset(offset)
        if die is None:
            return None
        return self._resolve_primitive_die(search_name, die)

    def _lookup_primitive_offset(self: TypeResolverContext, type_name: str) -> int | None:
        offset = self.index.find_symbol_offset(type_name)
        if isinstance(offset, int):
            return offset
        result = self.index.targeted_symbol_search(type_name)
        if result.status is not SearchStatus.COMPLETE:
            logger.debug(
                "Primitive search for %s ended as %s: %s",
                type_name,
                result.status.value,
                "; ".join(result.diagnostics),
            )
            return None
        return result.die_offset

    def _resolve_primitive_die(
        self: TypeResolverContext, type_name: str, die: DwarfEntry
    ) -> str | None:
        if die.tag == "DW_TAG_base_type":
            return type_name
        if die.tag != "DW_TAG_typedef":
            return None
        if "DW_AT_type" not in die.attributes:
            return None
        target_die = die.get_DIE_from_attribute("DW_AT_type")
        return self._get_primitive_base_type_name(target_die) if target_die else None

    def _get_base_type_from_typename(self: TypeResolverContext, type_name: str) -> str | None:
        """Resolve a type name through the indexed DIE chain, when available."""
        if not self.index:
            return None
        try:
            offset = self.index.find_symbol_offset(type_name)
            if offset is None:
                return None
            die = self.index.get_die_by_offset(offset)
            return self._get_primitive_base_type_name(die) if die else None
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.debug(
                "Error in DWARF DIE traversal for %s: %s", type_name, error, exc_info=error
            )
            return None

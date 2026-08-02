"""Symbol discovery operations for the lazy DWARF index."""

from __future__ import annotations

from typing import Any

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry, decode_dwarf_string
from ...core.observability import get_logger
from ..models.dwarf.tag_registry import DwarfTagRegistry
from .lazy_index_context import LazyIndexContext

logger = get_logger(__name__)


class LazyIndexDiscoveryMixin:
    def _get_default_target_types(self: LazyIndexContext) -> set[str]:
        return set(DwarfTagRegistry.ALL_SEARCHABLE_TAGS)

    def _get_symbol_type(self: LazyIndexContext, die_tag: str) -> str:
        return die_tag if DwarfTagRegistry.is_searchable_tag(die_tag) else "DW_TAG_other"

    @staticmethod
    def _extract_symbol_name(name_attr: Any) -> str:
        return decode_dwarf_string(name_attr.value)

    def _process_die_symbol(
        self: LazyIndexContext, die: DwarfEntry, cu_offset: int | None = None
    ) -> bool:
        name_attr = die.attributes.get("DW_AT_name")
        if name_attr is None:
            return False
        symbol_name = self._extract_symbol_name(name_attr)
        if cu_offset is None:
            self.persistent_cache.add_symbol(symbol_name, die.offset)
        else:
            self.persistent_cache.add_symbol_cu_mapping(symbol_name, cu_offset, die.offset)
        self._discovered_symbols.add(symbol_name)
        logger.debug("Discovered '%s' at 0x%x (tag: %s)", symbol_name, die.offset, die.tag)
        return True

    def discover_symbols_in_cu(
        self: LazyIndexContext, cu: DwarfCompilationUnit, target_types: set[str] | None = None
    ) -> int:
        """Discover searchable symbols in one CU without retaining its DIEs."""
        target_types = target_types or self._get_default_target_types()
        discovered = 0
        try:
            for die in cu.iter_DIEs():
                if die.tag in target_types and self._process_die_symbol(die, cu.cu_offset):
                    discovered += 1
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.error(
                "Error discovering symbols in CU at 0x%x: %s",
                cu.cu_offset,
                error,
                exc_info=error,
            )
        return discovered

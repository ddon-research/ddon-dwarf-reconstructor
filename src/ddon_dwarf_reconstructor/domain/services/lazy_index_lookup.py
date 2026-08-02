"""Offset and compilation-unit lookup operations for the lazy index."""

from __future__ import annotations

from typing import cast

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.observability import get_logger
from .lazy_index_context import LazyIndexContext

logger = get_logger(__name__)


class LazyIndexLookupMixin:
    def find_symbol_offset(self: LazyIndexContext, symbol_name: str) -> int | None:
        """Look up a symbol in the persistent index."""
        return self.persistent_cache.get_symbol_offset(symbol_name)

    def get_die_by_offset(self: LazyIndexContext, offset: int) -> DwarfEntry | None:
        """Resolve a DIE through the bounded runtime cache."""
        cached_die = cast(DwarfEntry | None, self.die_cache.get(offset))
        if cached_die is not None:
            return cached_die
        die = self._find_die_at_offset(offset)
        if die is not None:
            self.die_cache.put(offset, die)
        return die

    def _find_die_at_offset(self: LazyIndexContext, offset: int) -> DwarfEntry | None:
        """Use pyelftools' indexed reference lookup with a compatibility fallback."""
        try:
            if not self.dwarf_info:
                logger.error("DWARF info is None!")
                return None
            die = cast(DwarfEntry | None, self.dwarf_info.get_DIE_from_refaddr(offset))
            if die is None:
                return None
            if die.offset == offset:
                logger.debug("Found DIE at offset 0x%x: %s", offset, die.tag)
                return die
            logger.warning(
                "Indexed lookup returned offset %r for 0x%x; using compatibility scan",
                die.offset,
                offset,
            )
            return self._scan_die_at_offset(offset)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.error("Error finding DIE at offset 0x%x: %s", offset, error)
            return None

    def _scan_die_at_offset(self: LazyIndexContext, offset: int) -> DwarfEntry | None:
        """Scan only the CU whose bounds contain the requested offset."""
        for cu in self.dwarf_info.iter_CUs():
            if cu.cu_offset <= offset < cu.cu_offset + cu["unit_length"] + 4:
                return self._find_die_in_cu(cu, offset)
        return None

    @staticmethod
    def _find_die_in_cu(cu: DwarfCompilationUnit, offset: int) -> DwarfEntry | None:
        for die in cu.iter_DIEs():
            if die.offset == offset:
                return die
        return None

    def _get_cu_by_offset(self: LazyIndexContext, cu_offset: int) -> DwarfCompilationUnit | None:
        """Return the compilation unit with the requested offset."""
        try:
            for cu in self.dwarf_info.iter_CUs():
                if cu.cu_offset == cu_offset:
                    return cu
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.error("Error finding CU at offset 0x%x: %s", cu_offset, error)
        return None

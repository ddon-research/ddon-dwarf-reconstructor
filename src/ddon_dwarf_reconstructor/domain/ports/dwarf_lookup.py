"""Compatibility lookup contract for the explicit legacy validation producer."""

from __future__ import annotations

from typing import Protocol

from ...core.dwarf import DwarfEntry
from ..services.search_result import SearchResult
from .cache import SymbolCachePort


class DwarfLookupPort(Protocol):
    """Offset lookup operations retained behind the validation/live adapter boundary."""

    persistent_cache: SymbolCachePort

    def find_symbol_offset(self, symbol_name: str) -> int | None: ...

    def targeted_symbol_search(
        self, symbol_name: str, timeout: float | None = None
    ) -> SearchResult: ...

    def get_die_by_offset(self, offset: int) -> DwarfEntry | None: ...

    def save_cache(self) -> None: ...

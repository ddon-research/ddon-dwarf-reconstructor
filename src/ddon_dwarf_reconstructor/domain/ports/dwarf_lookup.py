"""Bounded symbol lookup contract implemented by source-bound adapters."""

from __future__ import annotations

from typing import Protocol

from ...core.dwarf import DwarfEntry
from ..models.analytical_dwarf import QueryResult
from ..services.search_result import SearchResult
from .cache import SymbolCachePort


class DwarfLookupPort(Protocol):
    """Offset lookup operations shared by canonical and validation adapters."""

    persistent_cache: SymbolCachePort

    def find_symbol_offset(self, symbol_name: str) -> int | None: ...

    def find_definition_tag(self, symbol_name: str) -> QueryResult: ...

    def targeted_symbol_search(
        self, symbol_name: str, timeout: float | None = None
    ) -> SearchResult: ...

    def get_die_by_offset(self, offset: int) -> DwarfEntry | None: ...

    def save_cache(self) -> None: ...

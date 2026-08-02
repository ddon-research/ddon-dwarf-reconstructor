"""Narrow port for offset-based DWARF index access."""

from __future__ import annotations

from typing import Protocol

from ...core.dwarf import DwarfEntry
from .cache import SymbolCachePort


class DwarfIndexPort(Protocol):
    """Operations required by parsing and type-resolution services."""

    persistent_cache: SymbolCachePort

    def find_symbol_offset(self, symbol_name: str) -> int | None: ...

    def targeted_symbol_search(self, symbol_name: str, timeout: float = 600.0) -> int | None: ...

    def get_die_by_offset(self, offset: int) -> DwarfEntry | None: ...

    def save_cache(self) -> None: ...

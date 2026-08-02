"""Outbound cache conversations required by the DWARF index workflow."""

from __future__ import annotations

from typing import Any, Protocol


class SymbolCachePort(Protocol):
    """Source-bound symbol/index cache operations used by the core."""

    def get_symbol_offset(self, symbol_name: str) -> int | None: ...

    def get_symbol_cu_offset(self, symbol_name: str) -> int | None: ...

    def add_symbol(self, symbol_name: str, offset: int) -> None: ...

    def add_symbol_cu_mapping(
        self,
        symbol_name: str,
        cu_offset: int,
        die_offset: int,
        score: int = 0,
        complete: bool = True,
    ) -> None: ...

    def save(self) -> None: ...

    def get_statistics(self) -> dict[str, Any]: ...

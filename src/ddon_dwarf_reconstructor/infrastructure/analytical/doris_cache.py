"""Cache-compatible view over the durable Doris definition index."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...domain.ports.cache import SymbolCachePort
from .doris_models import DorisDie

if TYPE_CHECKING:
    from .doris_store import DorisDwarfStore


class DorisCache(SymbolCachePort):
    """Expose Doris definition lookups through the cache port."""

    def __init__(self, store: DorisDwarfStore) -> None:
        self._store = store

    def get_symbol_offset(self, symbol_name: str) -> int | None:
        result = self._store.find_primary_definition(symbol_name)
        item = result.items[0] if result.items else None
        return item.offset if isinstance(item, DorisDie) else None

    def get_symbol_cu_offset(self, symbol_name: str) -> int | None:
        result = self._store.find_primary_definition(symbol_name)
        item = result.items[0] if result.items else None
        return item.cu.cu_offset if isinstance(item, DorisDie) else None

    def get_symbol_completeness(self, symbol_name: str) -> bool | None:
        result = self._store.find_primary_definition(symbol_name)
        if not result.items or not isinstance(result.items[0], DorisDie):
            return None
        return "DW_AT_declaration" not in result.items[0].attributes

    def add_symbol(self, symbol_name: str, offset: int) -> None:
        del symbol_name, offset

    def add_symbol_cu_mapping(
        self,
        symbol_name: str,
        cu_offset: int,
        die_offset: int,
        score: int = 0,
        complete: bool = True,
    ) -> None:
        del symbol_name, cu_offset, die_offset, score, complete

    def save(self) -> None:
        return

    def get_statistics(self) -> dict[str, Any]:
        return {
            "backend": "doris",
            "durable": True,
            "source_id": self._store.manifest.source_identity.sha256,
        }

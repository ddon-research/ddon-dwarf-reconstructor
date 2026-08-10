"""Generator-facing index adapter over the Doris analytical store."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import (
    DefinitionCandidate,
    DefinitionSignals,
    score_definition,
)
from ...domain.services.search_result import SearchResult, SearchStatus
from .doris_models import DorisDie

if TYPE_CHECKING:
    from .doris_store import DorisDwarfStore


class DorisDwarfIndex:
    """Generator lookup adapter backed by Doris's durable indexes."""

    persistent_cache: SymbolCachePort

    def __init__(self, store: DorisDwarfStore) -> None:
        self.store = store
        self.persistent_cache = store.persistent_cache

    def find_symbol_offset(self, symbol_name: str) -> int | None:
        result = self.store.find_primary_definition(symbol_name)
        item = result.items[0] if result.items else None
        return item.offset if isinstance(item, DorisDie) else None

    def targeted_symbol_search(
        self, symbol_name: str, timeout: float | None = None
    ) -> SearchResult:
        del timeout
        started = perf_counter()
        result = self.store.find_primary_definition(symbol_name)
        candidate = (
            self._candidate(symbol_name, result.items[0], self.store)
            if result.items and isinstance(result.items[0], DorisDie)
            else None
        )
        return SearchResult(
            status=SearchStatus.COMPLETE if candidate is not None else SearchStatus.NOT_FOUND,
            candidate=candidate,
            elapsed_seconds=perf_counter() - started,
            cus_searched=self.store.unit_count,
        )

    def get_die_by_offset(self, offset: int) -> DorisDie | None:
        return self.store.die_by_offset(offset)

    def save_cache(self) -> None:
        return

    @staticmethod
    def _candidate(symbol_name: str, die: DorisDie, store: DorisDwarfStore) -> DefinitionCandidate:
        byte_size = _attribute_int(die, "DW_AT_byte_size") or 0
        declaration = "DW_AT_declaration" in die.attributes
        score = score_definition(
            DefinitionSignals(
                tag=str(die.tag),
                byte_size=byte_size,
                has_children=die.has_children,
                is_declaration=declaration,
                has_type_reference="DW_AT_type" in die.attributes,
                nested=store.child_tag_counts(die.offset),
            )
        )
        return DefinitionCandidate(
            symbol=symbol_name,
            cu_offset=die.cu.cu_offset,
            die_offset=die.offset,
            score=score,
            complete=not declaration and score >= 0,
            byte_size=byte_size,
            has_children=die.has_children,
            is_declaration=declaration,
            has_type_reference="DW_AT_type" in die.attributes,
        )


def _attribute_int(die: DorisDie, name: str) -> int | None:
    attribute = die.attributes.get(name)
    value = attribute.value if attribute is not None else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["DorisDwarfIndex"]

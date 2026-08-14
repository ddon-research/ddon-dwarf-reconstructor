"""Generator-facing index adapter over the Doris analytical store."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Protocol

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import (
    DefinitionSignals,
    NestedTypeCounts,
    build_definition_candidate,
)
from ...domain.services.search_result import SearchResult, SearchStatus, search_status_for_query
from .doris_models import DorisDie
from .doris_store_helpers import bounded_query_diagnostic

if TYPE_CHECKING:
    from .doris_store import DorisDwarfStore


class DorisCandidateStore(Protocol):
    """Minimal store surface required by canonical candidate scoring."""

    def child_tag_counts(self, die_offset: int) -> NestedTypeCounts: ...


class DorisDwarfIndex:
    """Generator lookup adapter backed by Doris's durable indexes."""

    persistent_cache: SymbolCachePort

    def __init__(self, store: DorisDwarfStore) -> None:
        self.store = store
        self.persistent_cache = store.persistent_cache

    def find_symbol_offset(self, symbol_name: str) -> int | None:
        """Return the source-bound primary offset hint for one symbol.

        Partial or unavailable query results cannot provide a cache hint.  The
        caller must use :meth:`targeted_symbol_search` when it needs explicit
        search evidence and status.
        """
        result = self.store.find_primary_definition(symbol_name)
        if result.status is not QueryStatus.COMPLETE:
            return None
        item = result.items[0] if result.items else None
        return item.offset if isinstance(item, DorisDie) else None

    def find_definition_tag(self, symbol_name: str) -> QueryResult:
        """Return a tag only when the complete tag aggregate is unambiguous."""
        try:
            tags = self.store.definition_tags(symbol_name)
        except Exception as error:
            return QueryResult(
                QueryStatus.UNAVAILABLE,
                diagnostics=(bounded_query_diagnostic(error),),
            )
        if len(tags) != 1:
            status = QueryStatus.NOT_FOUND if not tags else QueryStatus.PARTIAL
            diagnostics = () if not tags else ("definition tags are ambiguous",)
            return QueryResult(status, tuple(tags), diagnostics=diagnostics)
        return QueryResult(QueryStatus.COMPLETE, tags)

    def targeted_symbol_search(
        self, symbol_name: str, timeout: float | None = None
    ) -> SearchResult:
        del timeout
        started = perf_counter()
        try:
            result = self.store.find_primary_definition(symbol_name)
        except Exception as error:
            return SearchResult(
                status=SearchStatus.UNAVAILABLE,
                candidate=None,
                elapsed_seconds=perf_counter() - started,
                cus_searched=0,
                diagnostics=(bounded_query_diagnostic(error),),
            )
        candidate = (
            self._candidate(symbol_name, result.items[0], self.store)
            if result.items and isinstance(result.items[0], DorisDie)
            else None
        )
        return SearchResult(
            status=search_status_for_query(result.status),
            candidate=candidate,
            elapsed_seconds=perf_counter() - started,
            cus_searched=self.store.unit_count,
            diagnostics=result.diagnostics,
        )

    def get_die_by_offset(self, offset: int) -> DorisDie | None:
        return self.store.die_by_offset(offset)

    def save_cache(self) -> None:
        return

    @staticmethod
    def _candidate(symbol_name: str, die: DorisDie, store: DorisDwarfStore):
        return build_doris_candidate(symbol_name, die, store)


def build_doris_candidate(symbol_name: str, die: DorisDie, store: DorisCandidateStore):
    """Build a candidate through the canonical domain scoring policy."""
    byte_size = _attribute_int(die, "DW_AT_byte_size") or 0
    declaration = "DW_AT_declaration" in die.attributes
    return build_definition_candidate(
        symbol_name,
        cu_offset=die.cu.cu_offset,
        die_offset=die.offset,
        signals=DefinitionSignals(
            tag=str(die.tag),
            byte_size=byte_size,
            has_children=die.has_children,
            is_declaration=declaration,
            has_type_reference="DW_AT_type" in die.attributes,
            nested=store.child_tag_counts(die.offset),
        ),
    )


def _attribute_int(die: DorisDie, name: str) -> int | None:
    attribute = die.attributes.get(name)
    value = attribute.value if attribute is not None else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["DorisCandidateStore", "DorisDwarfIndex", "build_doris_candidate"]

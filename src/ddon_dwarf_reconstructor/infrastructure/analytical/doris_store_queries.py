"""Typed query collaborator for the Doris-backed analytical store."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from ...domain.models.analytical_dwarf import MaterializationManifest, QueryResult, QueryStatus
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import (
    DefinitionSignals,
    NestedTypeCounts,
    definition_candidate_sort_key,
    is_early_exit_candidate,
)
from .bounded_query_cache import BoundedQueryCache
from .doris import DorisConfig
from .doris_hydration import _DorisHydrationStore, hydrate_dies_by_keys, prime_child_tag_counts
from .doris_index import DorisCandidateStore, build_doris_candidate
from .doris_models import DorisCompilationUnit, DorisDie
from .doris_queries import DorisQueryExecutor
from .doris_store_helpers import (
    bounded_query_diagnostic,
    definition_has_name,
    definition_matches,
    optional_int,
    query_status,
    result,
    unavailable,
)
from .store_selection import prefer_cached_definition


class DorisStoreQueryPort(_DorisHydrationStore, DorisCandidateStore, Protocol):
    """Store state and operations needed by the typed query collaborator."""

    manifest_path: Path
    manifest: MaterializationManifest
    _config: DorisConfig
    _queries: DorisQueryExecutor
    _definition_query_cache: BoundedQueryCache[
        tuple[str, str | None, frozenset[str] | None], QueryResult
    ]
    _die_unit_offsets: dict[int, int]
    _child_tag_counts: dict[int, NestedTypeCounts]
    _selection_cache: SymbolCachePort | None

    def record_cache_hit(self) -> None: ...

    def record_cache_miss(self) -> None: ...

    def compilation_unit_by_offset(self, unit_offset: int) -> DorisCompilationUnit: ...

    def die_by_offset(self, die_offset: int | None) -> DorisDie | None: ...

    def children_for_die(self, die_offset: int) -> Iterable[DorisDie]: ...

    def _die_from_index_record(self, record: dict[str, object]) -> DorisDie | None: ...

    def _rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
        operation: str = "family_rows",
    ) -> tuple[dict[str, Any], ...]: ...


class DorisStoreQueryOperations:
    """Execute result shaping and definition policy over one Doris store view."""

    def __init__(self, store: DorisStoreQueryPort) -> None:
        self._store = store

    def get_compilation_unit(self, unit_offset: int) -> QueryResult:
        store = self._store
        try:
            try:
                item = store.compilation_unit_by_offset(unit_offset)
            except KeyError:
                item = None
            return result(item, store.manifest_path, store.manifest.status)
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def get_die(self, die_offset: int) -> QueryResult:
        store = self._store
        try:
            return result(
                store.die_by_offset(die_offset), store.manifest_path, store.manifest.status
            )
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def _definition_items(
        self,
        records: Sequence[dict[str, object]],
        *,
        name: str,
        qualified_name: str | None,
        tags: frozenset[str] | None,
    ) -> tuple[DorisDie, ...]:
        store = self._store
        hydrate_dies_by_keys(
            store,
            (
                (unit_offset, die_offset)
                for record in records
                if (unit_offset := optional_int(record.get("unit_offset"))) is not None
                and (die_offset := optional_int(record.get("die_offset"))) is not None
            ),
        )
        items = tuple(
            die
            for record in records
            if (die := store._die_from_index_record(record)) is not None
            and definition_matches(die, qualified_name, tags)
        )
        prime_child_tag_counts(store, items)
        ordered = tuple(sorted(items, key=lambda die: _definition_sort_key(store, die)))
        return prefer_cached_definition(name, ordered, store._selection_cache)

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        store = self._store
        cache_key = (name, qualified_name, tags)
        cached = store._definition_query_cache.lookup(cache_key)
        if cached is not None:
            store.record_cache_hit()
            return cached
        store.record_cache_miss()
        try:
            bounded = store._queries.find_definition_rows_bounded(
                name,
                tags=tuple(sorted(tags)) if tags else (),
                limit=1001,
            )
            items = self._definition_items(
                bounded.rows,
                name=name,
                qualified_name=qualified_name,
                tags=tags,
            )
            status = query_status(bool(items), store.manifest.status, truncated=bounded.truncated)
            diagnostics = (
                ("definition query reached its safety bound",) if bounded.truncated else ()
            )
            query = QueryResult(
                status,
                items,
                (str(store.manifest_path),),
                diagnostics,
                bounded.truncated,
            )
        except Exception as error:
            query = QueryResult(
                QueryStatus.UNAVAILABLE,
                (),
                (str(store.manifest_path),),
                (bounded_query_diagnostic(error, prefix="Doris definition query unavailable"),),
            )
        store._definition_query_cache[cache_key] = query
        return query

    def find_primary_definition(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        cached = self._cached_primary_definition(name, qualified_name, tags)
        if cached is not None:
            return result(cached, self._store.manifest_path, self._store.manifest.status)
        query = self.find_definitions(name, qualified_name=qualified_name, tags=tags)
        if query.truncated:
            early = self._early_primary_definition(query, name)
            if early is not None:
                return early
            query = self._complete_definition_query(
                name,
                qualified_name=qualified_name,
                tags=tags,
            )
        return QueryResult(
            query.status,
            query.items[:1],
            query.provenance,
            query.diagnostics,
            query.truncated,
        )

    def _early_primary_definition(self, query: QueryResult, name: str) -> QueryResult | None:
        """Accept a bounded result only when the shared early-exit proof holds."""
        store = self._store
        die = query.items[0] if query.items else None
        if not isinstance(die, DorisDie):
            return None
        candidate = build_doris_candidate(name, die, store)
        signals = DefinitionSignals(
            tag=str(die.tag),
            byte_size=candidate.byte_size,
            has_children=candidate.has_children,
            is_declaration=candidate.is_declaration,
            has_type_reference=candidate.has_type_reference,
            nested=store.child_tag_counts(die.offset),
        )
        if not is_early_exit_candidate(signals, candidate.score):
            return None
        return QueryResult(
            QueryStatus.COMPLETE,
            (die,),
            query.provenance,
            ("bounded early-exit candidate satisfied selection policy",),
        )

    def _complete_definition_query(
        self,
        name: str,
        *,
        qualified_name: str | None,
        tags: frozenset[str] | None,
    ) -> QueryResult:
        """Retry a truncated bounded query through a larger bounded window."""
        store = self._store
        try:
            bounded = store._queries.find_definition_rows_complete(
                name,
                tags=tuple(sorted(tags)) if tags else (),
            )
            items = self._definition_items(
                bounded.rows,
                name=name,
                qualified_name=qualified_name,
                tags=tags,
            )
            status = query_status(bool(items), store.manifest.status, truncated=bounded.truncated)
            diagnostics = (
                ("complete definition query reached its safety bound",) if bounded.truncated else ()
            )
            return QueryResult(
                status,
                items,
                (str(store.manifest_path),),
                diagnostics,
                bounded.truncated,
            )
        except Exception as error:
            return QueryResult(
                QueryStatus.UNAVAILABLE,
                (),
                (str(store.manifest_path),),
                (
                    bounded_query_diagnostic(
                        error,
                        prefix="Doris complete definition query unavailable",
                    ),
                ),
            )

    def _cached_primary_definition(
        self,
        name: str,
        qualified_name: str | None,
        tags: frozenset[str] | None,
    ) -> DorisDie | None:
        """Hydrate a validated source-bound selection without widening a bounded query."""
        store = self._store
        cache = store._selection_cache
        if cache is None or qualified_name is not None or tags is not None:
            return None
        if cache.get_symbol_completeness(name) is False:
            return None
        offset = cache.get_symbol_offset(name)
        if not isinstance(offset, int):
            return None
        die = store.die_by_offset(offset)
        if die is None or "DW_AT_declaration" in die.attributes:
            return None
        return die if definition_has_name(die, name) else None

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        store = self._store
        try:
            records = store._rows(
                "index",
                {
                    "index_type": "method_implementation",
                    "target_offset": declaration_offset,
                    "resolution_status": QueryStatus.COMPLETE.value,
                },
                columns=(
                    "source_id",
                    "unit_offset",
                    "die_offset",
                    "index_type",
                    "name",
                    "tag",
                    "target_offset",
                    "resolution_status",
                ),
                order_by=("unit_offset", "die_offset"),
                table_name=store._config.method_lookup_table,
            )
            for record in records:
                die = store._die_from_index_record(record)
                if die is not None:
                    return result(die, store.manifest_path, store.manifest.status)
            return result(None, store.manifest_path, store.manifest.status)
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def children(self, die_offset: int) -> QueryResult:
        store = self._store
        try:
            items = tuple(store.children_for_die(die_offset))
            return QueryResult(
                query_status(bool(items), store.manifest.status),
                items,
                (str(store.manifest_path),),
            )
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def parent(self, die_offset: int) -> QueryResult:
        store = self._store
        try:
            die = store.die_by_offset(die_offset)
            return result(
                die.get_parent() if die is not None else None,
                store.manifest_path,
                store.manifest.status,
            )
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def references(self, die_offset: int) -> QueryResult:
        store = self._store
        try:
            unit_offset = store._die_unit_offsets.get(die_offset)
            filters: dict[str, object] = {"die_offset": die_offset}
            if unit_offset is not None:
                filters["unit_offset"] = unit_offset
            items = store._rows("reference", filters, order_by=("attribute_name", "relation"))
            return QueryResult(
                query_status(bool(items), store.manifest.status),
                items,
                (str(store.manifest_path),),
            )
        except Exception as error:
            return unavailable(error, store.manifest_path)

    def child_tag_counts(self, die_offset: int) -> NestedTypeCounts:
        store = self._store
        cached = store._child_tag_counts.get(die_offset)
        if cached is not None:
            store.record_cache_hit()
            return cached
        store.record_cache_miss()
        rows = store._rows("die", {"parent_offset": die_offset}, columns=("tag", "is_null"))
        counts = {"DW_TAG_enumeration_type": 0, "DW_TAG_structure_type": 0, "DW_TAG_union_type": 0}
        for row in rows:
            tag = row.get("tag")
            if not row.get("is_null") and tag in counts:
                counts[tag] += 1
        result_value = NestedTypeCounts(
            enums=counts["DW_TAG_enumeration_type"],
            structs=counts["DW_TAG_structure_type"],
            unions=counts["DW_TAG_union_type"],
        )
        store._child_tag_counts[die_offset] = result_value
        return result_value


def _definition_sort_key(store: DorisStoreQueryPort, die: DorisDie) -> tuple[int, int, int, int]:
    candidate = build_doris_candidate("", die, store)
    return definition_candidate_sort_key(candidate, depth=die.depth)


__all__ = ["DorisStoreQueryOperations", "DorisStoreQueryPort"]

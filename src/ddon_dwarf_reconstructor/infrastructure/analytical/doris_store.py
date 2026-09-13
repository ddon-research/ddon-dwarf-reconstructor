"""Doris-backed analytical query store used by generation."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...core.content_hash import sha256_file
from ...core.dwarf import DwarfInfo
from ...core.observability import get_logger, log_event
from ...domain.models.analytical_dwarf import (
    MaterializationManifest,
    QueryResult,
    QueryStatus,
)
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import NestedTypeCounts
from .bounded_query_cache import BoundedQueryCache
from .doris import DorisConfig
from .doris_batch_rows import hydration_rows
from .doris_cache import DorisCache
from .doris_connection import connect_sql
from .doris_hydration import (
    prefetch_children,
    prefetch_dies,
)
from .doris_method_queries import DorisMethodQueries
from .doris_models import (
    DorisCompilationUnit,
    DorisDie,
    DorisDwarfInfo,
)
from .doris_queries import DorisQueryExecutor
from .doris_reference_hydration import (
    prefetch_references,
    reference_candidates,
)
from .doris_registry import DorisRegistrySnapshot, validate_registry
from .doris_serving_profile import DorisServingProfile
from .doris_store_access import DorisStoreAccessMixin
from .doris_store_helpers import optional_int as _optional_int
from .doris_store_hydration import DorisStoreHydrationMixin
from .doris_store_queries import DorisStoreQueryOperations
from .doris_store_runtime import DorisStoreRuntimeMixin
from .doris_store_runtime import runtime_cache_size as _runtime_cache_size
from .doris_store_runtime import validate_runtime_manifest as _validate_runtime_manifest
from .doris_store_runtime import verify_source_binding as _verify_source_binding
from .dwarf_reference import reference_target_for_attribute
from .line_program import StoreLineProgram
from .manifest import load_manifest
from .store_selection import load_selection_cache

logger = get_logger(__name__)
_DEFAULT_DIE_CACHE_SIZE = 1_048_576
_DEFAULT_CHILD_CACHE_SIZE = 262_144
_DEFAULT_REFERENCE_CACHE_SIZE = 524_288
_DEFAULT_DEFINITION_CACHE_SIZE = 65_536


class DorisDwarfStore(
    DorisStoreHydrationMixin,
    DorisStoreRuntimeMixin,
    DorisStoreAccessMixin,
    DorisMethodQueries,
):
    """Lazy, source-bound query façade over normalized Doris family tables."""

    def __init__(
        self,
        manifest_path: Path,
        manifest: MaterializationManifest,
        connection: Any,
        config: DorisConfig,
        *,
        selection_cache: SymbolCachePort | None = None,
        registry: DorisRegistrySnapshot | None = None,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.manifest = manifest
        self.manifest_sha256 = sha256_file(self.manifest_path)
        self._connection = connection
        self._config = config
        self._source_id = manifest.source_identity.sha256
        self._name_lookup_table = config.effective_name_lookup_table
        self._selection_cache = selection_cache
        self.registry = registry
        self._queries = DorisQueryExecutor(connection, config, self._source_id)
        die_cache_size = _runtime_cache_size("DDON_DORIS_DIE_CACHE_SIZE", _DEFAULT_DIE_CACHE_SIZE)
        child_cache_size = _runtime_cache_size(
            "DDON_DORIS_CHILD_CACHE_SIZE", _DEFAULT_CHILD_CACHE_SIZE
        )
        reference_cache_size = _runtime_cache_size(
            "DDON_DORIS_REFERENCE_CACHE_SIZE", _DEFAULT_REFERENCE_CACHE_SIZE
        )
        definition_cache_size = _runtime_cache_size(
            "DDON_DORIS_DEFINITION_CACHE_SIZE", _DEFAULT_DEFINITION_CACHE_SIZE
        )
        self._init_query_caches(die_cache_size, child_cache_size, reference_cache_size)
        self._reference_prefetch = config.reference_prefetch
        self._attribute_projection = config.attribute_projection
        self._child_tag_filter = config.child_tag_filter
        self._hydration_scope = config.hydration_scope
        self._definition_query_cache = BoundedQueryCache(max_size=definition_cache_size)
        self._definition_name_count_cache: int | None = None
        self._active_root: str | None = None
        self._cache_hits = 0
        self._cache_misses = 0
        self._closed = False
        self._query_operations = DorisStoreQueryOperations(self)
        self.dwarf_info: DwarfInfo = DorisDwarfInfo(self)
        self.persistent_cache = DorisCache(self)

    def _init_query_caches(self, die_size: int, child_size: int, ref_size: int) -> None:
        self._units: BoundedQueryCache[int, DorisCompilationUnit] = BoundedQueryCache(
            max_size=child_size
        )
        self._dies: BoundedQueryCache[int, DorisDie] = BoundedQueryCache(max_size=die_size)
        self._dies_by_key: BoundedQueryCache[tuple[int, int], DorisDie] = BoundedQueryCache(
            max_size=die_size
        )
        self._die_unit_offsets: BoundedQueryCache[int, int] = BoundedQueryCache(max_size=die_size)
        self._children: BoundedQueryCache[int, tuple[DorisDie, ...]] = BoundedQueryCache(
            max_size=child_size
        )
        self._children_by_key: BoundedQueryCache[tuple[int, int], tuple[DorisDie, ...]] = (
            BoundedQueryCache(max_size=child_size)
        )
        self._line_programs: BoundedQueryCache[int, StoreLineProgram | None] = BoundedQueryCache(
            max_size=child_size
        )
        self._child_tag_counts: BoundedQueryCache[int, NestedTypeCounts] = BoundedQueryCache(
            max_size=die_size
        )
        self._child_tag_counts_by_key: BoundedQueryCache[tuple[int, int], NestedTypeCounts] = (
            BoundedQueryCache(max_size=die_size)
        )
        self._reference_targets: BoundedQueryCache[tuple[int | None, int, str], int | None] = (
            BoundedQueryCache(max_size=ref_size)
        )
        self._reference_loaded: set[tuple[int, int]] = set()
        self._reference_dies: BoundedQueryCache[int, None] = BoundedQueryCache(max_size=ref_size)
        self._reference_dies_by_key: BoundedQueryCache[tuple[int, int], None] = BoundedQueryCache(
            max_size=ref_size
        )

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        *,
        config: DorisConfig | None = None,
        verify_source: bool = True,
        source_path: Path | None = None,
        selection_cache_path: Path | None = None,
        selection_source_fingerprint: dict[str, int | str] | None = None,
    ) -> DorisDwarfStore:
        """Open a complete manifest's already-published Doris projection."""
        manifest_path = manifest_path.resolve()
        manifest = load_manifest(manifest_path)
        _validate_runtime_manifest(manifest, manifest_path)
        if verify_source:
            _verify_source_binding(manifest, source_path)
        config = config or DorisConfig.from_environment()
        connection = connect_sql(
            config,
            database=config.database,
        )
        try:
            serving_variant = DorisServingProfile.from_config(
                config,
                source_id=manifest.source_identity.sha256,
                schema_version=manifest.schema_version,
            )
            registry = validate_registry(
                connection,
                config.database,
                config.table,
                manifest,
                serving_variant_id=serving_variant.variant_id,
                serving_variant_configuration_sha256=serving_variant.configuration_sha256,
            )
            selection_cache = load_selection_cache(
                manifest,
                selection_cache_path,
                source_fingerprint=selection_source_fingerprint,
            )
            return cls(
                manifest_path,
                manifest,
                connection,
                config,
                selection_cache=selection_cache,
                registry=registry,
            )
        except BaseException:
            connection.close()
            raise

    def close(self) -> None:
        """Close the serving connection owned by this store."""
        if self._closed:
            return
        self._closed = True
        try:
            self._queries.close()
        finally:
            self._connection.close()

    def begin_root(self, root_symbol: str) -> None:
        """Reset request-scoped hydration state before one root is generated."""
        sizes = self._request_cache_sizes()
        log_event(
            logger,
            logging.DEBUG,
            "doris_root_cache_reset",
            root_symbol=root_symbol,
            previous_sizes=sizes,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
        )
        self._units.clear()
        self._dies.clear()
        self._dies_by_key.clear()
        self._die_unit_offsets.clear()
        self._children.clear()
        self._children_by_key.clear()
        self._line_programs.clear()
        self._child_tag_counts.clear()
        self._child_tag_counts_by_key.clear()
        self._reference_targets.clear()
        self._reference_loaded.clear()
        self._reference_dies.clear()
        self._reference_dies_by_key.clear()
        self._definition_query_cache.clear()
        self._active_root = root_symbol
        self._cache_hits = 0
        self._cache_misses = 0

    def end_root(self) -> None:
        """Record request-scoped cache usage after one root has completed."""
        if self._active_root is None:
            return
        log_event(
            logger,
            logging.DEBUG,
            "doris_root_cache_closed",
            root_symbol=self._active_root,
            final_sizes=self._request_cache_sizes(),
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
        )
        self._active_root = None

    def get_compilation_unit(self, unit_offset: int) -> QueryResult:
        return self._query_operations.get_compilation_unit(unit_offset)

    def get_die(self, die_offset: int) -> QueryResult:
        return self._query_operations.get_die(die_offset)

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        return self._query_operations.find_definitions(
            name,
            qualified_name=qualified_name,
            tags=tags,
        )

    def find_primary_definition(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        return self._query_operations.find_primary_definition(
            name,
            qualified_name=qualified_name,
            tags=tags,
        )

    def definition_tags(self, name: str) -> tuple[str, ...]:
        """Return complete aggregate-tag metadata for one source-bound name."""
        return self._queries.find_definition_tags(name)

    def children(self, die_offset: int) -> QueryResult:
        return self._query_operations.children(die_offset)

    def parent(self, die_offset: int) -> QueryResult:
        return self._query_operations.parent(die_offset)

    def references(self, die_offset: int) -> QueryResult:
        return self._query_operations.references(die_offset)

    def child_tag_counts(self, die_offset: int, unit_offset: int | None = None) -> NestedTypeCounts:
        return self._query_operations.child_tag_counts(die_offset, unit_offset)

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def _request_cache_sizes(self) -> dict[str, int]:
        return {
            "units": len(self._units),
            "dies": len(self._dies),
            "dies_by_key": len(self._dies_by_key),
            "die_unit_offsets": len(self._die_unit_offsets),
            "children": len(self._children),
            "children_by_key": len(self._children_by_key),
            "line_programs": len(self._line_programs),
            "child_tag_counts": len(self._child_tag_counts),
            "child_tag_counts_by_key": len(self._child_tag_counts_by_key),
            "reference_targets": len(self._reference_targets),
            "reference_loaded": len(self._reference_loaded),
            "reference_candidates": len(self._reference_dies),
            "reference_candidates_by_key": len(self._reference_dies_by_key),
            "definition_queries": len(self._definition_query_cache),
            "definition_query_evictions": self._definition_query_cache.evictions,
        }

    def die_by_offset(
        self, die_offset: int | None, unit_offset: int | None = None
    ) -> DorisDie | None:
        if die_offset is None:
            return None
        if unit_offset is not None:
            return self.die_by_key(unit_offset, die_offset)
        cached = self._dies.get(die_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        rows = tuple(
            hydration_rows(
                self,
                "die",
                {"die_offset": die_offset},
                columns=(
                    "unit_offset",
                    "die_offset",
                    "ordinal",
                    "tag",
                    "abbrev_code",
                    "has_children",
                    "depth",
                    "parent_offset",
                    "is_null",
                ),
                order_by=("unit_offset", "ordinal"),
                limit=1,
                table_name=self._config.die_lookup_table,
                operation="die_by_offset",
            )
        )
        if not rows:
            return None
        return self._die_from_record(rows[0])

    def die_by_key(self, unit_offset: int, die_offset: int) -> DorisDie | None:
        """Resolve one source/CU/DIE key without falling back to bare offsets."""
        key = (unit_offset, die_offset)
        exact = getattr(self, "_dies_by_key", None)
        cached = exact.get(key) if exact is not None else None
        if cached is not None:
            self.record_cache_hit()
            return cached
        legacy = self._dies.get(die_offset)
        if legacy is not None and self._die_unit_offsets.get(die_offset) == unit_offset:
            self.record_cache_hit()
            return legacy
        self.record_cache_miss()
        rows = tuple(
            hydration_rows(
                self,
                "die",
                {"unit_offset": unit_offset, "die_offset": die_offset},
                columns=(
                    "unit_offset",
                    "die_offset",
                    "ordinal",
                    "tag",
                    "abbrev_code",
                    "has_children",
                    "depth",
                    "parent_offset",
                    "is_null",
                ),
                limit=1,
                table_name=self._config.die_lookup_table,
                operation="die_by_key",
            )
        )
        return self._die_from_record(rows[0]) if rows else None

    def dies_for_unit(self, unit_offset: int) -> Iterable[DorisDie]:
        records = tuple(
            hydration_rows(
                self,
                "die",
                {"unit_offset": unit_offset},
                order_by=("ordinal",),
                operation="dies_for_unit",
            )
        )
        attributes = self._attributes_by_die(unit_offset, records)
        return tuple(
            self._die_from_record(record, attributes.get(int(record.get("die_offset", 0)), ()))
            for record in records
        )

    def children_for_die(
        self, die_offset: int, unit_offset: int | None = None
    ) -> Iterable[DorisDie]:
        parent, unit_offset = self._children_parent(die_offset, unit_offset)
        cached = self._cached_children(die_offset, unit_offset)
        if cached is not None:
            self.record_cache_hit()
            prefetch_children(self, cached)
            return iter(cached)
        self.record_cache_miss()
        if parent is not None and not parent.has_children:
            self._cache_children(die_offset, unit_offset, ())
            return iter(())
        filters: dict[str, object] = {"parent_offset": die_offset}
        if unit_offset is not None:
            filters["unit_offset"] = unit_offset
        records = tuple(
            hydration_rows(
                self,
                "die",
                filters,
                order_by=("ordinal",),
                operation="children_for_die",
            )
        )
        records = tuple(record for record in records if not record.get("is_null"))
        attributes = self._attributes_by_die(unit_offset, records)
        children = tuple(
            self._die_from_record(record, attributes.get(int(record.get("die_offset", 0)), ()))
            for record in records
        )
        self._cache_children(die_offset, unit_offset, children)
        prefetch_children(self, children)
        prefetch_dies(self, children)
        return iter(children)

    def _children_parent(
        self, die_offset: int, unit_offset: int | None
    ) -> tuple[DorisDie | None, int | None]:
        exact = getattr(self, "_dies_by_key", None)
        if exact is not None and unit_offset is not None:
            return exact.get((unit_offset, die_offset)), unit_offset
        parent = self._dies.get(die_offset)
        if parent is None:
            parent = self.die_by_offset(die_offset)
        resolved_unit = self._die_unit_offsets.get(die_offset)
        if resolved_unit is None and parent is not None:
            resolved_unit = parent.cu.cu_offset
        return parent, resolved_unit

    def _cached_children(
        self, die_offset: int, unit_offset: int | None
    ) -> tuple[DorisDie, ...] | None:
        exact = getattr(self, "_children_by_key", None)
        if exact is not None and unit_offset is not None:
            return exact.get((unit_offset, die_offset))
        return self._children.get(die_offset)

    def _cache_children(
        self, die_offset: int, unit_offset: int | None, children: tuple[DorisDie, ...]
    ) -> None:
        exact = getattr(self, "_children_by_key", None)
        if exact is not None and unit_offset is not None:
            exact[(unit_offset, die_offset)] = children
        if die_offset not in self._children:
            self._children[die_offset] = children

    def attribute_target(
        self, die_offset: int, attribute_name: str, unit_offset: int | None = None
    ) -> int | None:
        if unit_offset is None:
            unit_offset = self._die_unit_offsets.get(die_offset)
        cache_key = (unit_offset, die_offset, attribute_name)
        if cache_key in self._reference_targets:
            self.record_cache_hit()
            return self._reference_targets[cache_key]
        self.record_cache_miss()
        exact_dies = getattr(self, "_dies_by_key", None)
        cached_die = (
            exact_dies.get((unit_offset, die_offset))
            if exact_dies is not None and unit_offset is not None
            else self._dies.get(die_offset)
        )
        if cached_die is not None:
            target, status = reference_target_for_attribute(
                cached_die.attributes.get(attribute_name),
                unit_offset=unit_offset,
            )
            if status is QueryStatus.COMPLETE:
                self._reference_targets[cache_key] = target
                return target
            prefetch_references(self, reference_candidates(self, cached_die))
            if cache_key in self._reference_targets:
                self.record_cache_hit()
                return self._reference_targets[cache_key]
        filters: dict[str, object] = {
            "die_offset": die_offset,
            "attribute_name": attribute_name,
            "relation": "attribute_reference",
        }
        if unit_offset is not None:
            filters["unit_offset"] = unit_offset
        rows = tuple(
            hydration_rows(
                self,
                "reference",
                filters,
                columns=("target_offset",),
                limit=1,
                operation="attribute_target",
            )
        )
        target = rows[0].get("target_offset") if rows else None
        result = _optional_int(target)
        self._reference_targets[cache_key] = result
        return result

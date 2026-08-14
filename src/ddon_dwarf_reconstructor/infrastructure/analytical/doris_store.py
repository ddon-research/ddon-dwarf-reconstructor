"""Doris-backed analytical query store used by generation."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...core.dwarf import DwarfInfo
from ...core.observability import get_logger, log_event
from ...domain.models.analytical_dwarf import (
    MaterializationManifest,
    MaterializedUnit,
    QueryResult,
)
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import NestedTypeCounts
from ..artifacts import SourceIdentityCatalog
from .bounded_query_cache import BoundedQueryCache
from .doris import DorisConfig
from .doris_cache import DorisCache
from .doris_hydration import (
    attribute_projection_columns,
    attributes_by_die,
    prefetch_children,
    prefetch_dies,
    prefetch_references,
    reference_candidates,
)
from .doris_models import (
    DorisCompilationUnit,
    DorisDie,
    DorisDieData,
    DorisDwarfInfo,
)
from .doris_queries import DorisQueryExecutor
from .doris_registry import DorisRegistrySnapshot, validate_registry
from .doris_rows import restore_row
from .doris_serving_profile import DorisServingProfile
from .doris_store_helpers import optional_int as _optional_int
from .doris_store_helpers import optional_text as _optional_text
from .doris_store_queries import DorisStoreQueryOperations
from .line_program import StoreLineProgram, build_line_program
from .manifest import (
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
    validate_schema_version,
)
from .optional import import_optional
from .store_selection import load_selection_cache

logger = get_logger(__name__)


class DorisDwarfStore:
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
        self._connection = connection
        self._config = config
        self._source_id = manifest.source_identity.sha256
        self._name_lookup_table = config.effective_name_lookup_table
        self._selection_cache = selection_cache
        self.registry = registry
        self._queries = DorisQueryExecutor(connection, config, self._source_id)
        self._units: dict[int, DorisCompilationUnit] = {}
        self._dies: dict[int, DorisDie] = {}
        self._die_unit_offsets: dict[int, int] = {}
        self._children: dict[int, tuple[DorisDie, ...]] = {}
        self._line_programs: dict[int, StoreLineProgram | None] = {}
        self._child_tag_counts: dict[int, NestedTypeCounts] = {}
        self._reference_targets: dict[tuple[int | None, int, str], int | None] = {}
        self._reference_loaded: set[tuple[int, int]] = set()
        self._reference_prefetch = config.reference_prefetch
        self._attribute_projection = config.attribute_projection
        self._child_tag_filter = config.child_tag_filter
        self._hydration_scope = config.hydration_scope
        self._definition_query_cache = BoundedQueryCache()
        self._definition_name_count: int | None = None
        self._active_root: str | None = None
        self._cache_hits = 0
        self._cache_misses = 0
        self._closed = False
        self._query_operations = DorisStoreQueryOperations(self)
        self.dwarf_info: DwarfInfo = DorisDwarfInfo(self)
        self.persistent_cache = DorisCache(self)

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
        pymysql = import_optional("pymysql", "analytical")
        connection = pymysql.connect(
            host=config.sql_host,
            port=config.sql_port,
            user=config.user,
            password=config.password,
            database=config.database,
            autocommit=True,
            connect_timeout=config.sql_connect_timeout_seconds,
            read_timeout=config.sql_read_timeout_seconds,
            write_timeout=config.sql_write_timeout_seconds,
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
        self._die_unit_offsets.clear()
        self._children.clear()
        self._line_programs.clear()
        self._child_tag_counts.clear()
        self._reference_targets.clear()
        self._reference_loaded.clear()
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

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        return self._query_operations.find_method_implementation(declaration_offset)

    def children(self, die_offset: int) -> QueryResult:
        return self._query_operations.children(die_offset)

    def parent(self, die_offset: int) -> QueryResult:
        return self._query_operations.parent(die_offset)

    def references(self, die_offset: int) -> QueryResult:
        return self._query_operations.references(die_offset)

    def child_tag_counts(self, die_offset: int) -> NestedTypeCounts:
        return self._query_operations.child_tag_counts(die_offset)

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def _request_cache_sizes(self) -> dict[str, int]:
        return {
            "units": len(self._units),
            "dies": len(self._dies),
            "die_unit_offsets": len(self._die_unit_offsets),
            "children": len(self._children),
            "line_programs": len(self._line_programs),
            "child_tag_counts": len(self._child_tag_counts),
            "reference_targets": len(self._reference_targets),
            "reference_loaded": len(self._reference_loaded),
            "definition_queries": len(self._definition_query_cache),
            "definition_query_evictions": self._definition_query_cache.evictions,
        }

    def iter_compilation_units(self) -> Iterable[MaterializedUnit]:
        rows = self._rows("unit", order_by=("unit_offset",), operation="iter_compilation_units")
        for record in rows:
            header = record.get("header", {})
            yield MaterializedUnit(
                source_id=str(record.get("source_id", self._source_id)),
                unit_offset=int(record.get("unit_offset", 0)),
                unit_length=_optional_int(record.get("unit_length")),
                header=header if isinstance(header, dict) else {},
                unit_type=_optional_text(record.get("unit_type")),
                parser_status=_optional_text(record.get("parser_status")),
                details=record.get("details"),
            )

    def iter_dwarf_units(self) -> Iterable[DorisCompilationUnit]:
        for record in self._rows("unit", order_by=("unit_offset",), operation="iter_dwarf_units"):
            yield self._unit_from_record(record)

    def compilation_unit_by_offset(self, unit_offset: int) -> DorisCompilationUnit:
        cached = self._units.get(unit_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        rows = self._rows(
            "unit", {"unit_offset": unit_offset}, limit=1, operation="compilation_unit_by_offset"
        )
        if not rows:
            raise KeyError(f"Compilation unit 0x{unit_offset:x} is not published")
        return self._unit_from_record(rows[0])

    def die_by_offset(self, die_offset: int | None) -> DorisDie | None:
        if die_offset is None:
            return None
        cached = self._dies.get(die_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        rows = self._rows(
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
        if not rows:
            return None
        return self._die_from_record(rows[0])

    def dies_for_unit(self, unit_offset: int) -> Iterable[DorisDie]:
        records = self._rows(
            "die", {"unit_offset": unit_offset}, order_by=("ordinal",), operation="dies_for_unit"
        )
        attributes = self._attributes_by_die(unit_offset, records)
        return tuple(
            self._die_from_record(record, attributes.get(int(record.get("die_offset", 0)), ()))
            for record in records
        )

    def children_for_die(self, die_offset: int) -> Iterable[DorisDie]:
        cached = self._children.get(die_offset)
        if cached is not None:
            self.record_cache_hit()
            prefetch_children(self, cached)
            return iter(cached)
        self.record_cache_miss()
        parent = self._dies.get(die_offset)
        if parent is not None and not parent.has_children:
            self._children[die_offset] = ()
            return iter(())
        unit_offset = self._die_unit_offsets.get(die_offset)
        if unit_offset is None and parent is not None:
            unit_offset = parent.cu.cu_offset
        filters: dict[str, object] = {"parent_offset": die_offset}
        if unit_offset is not None:
            filters["unit_offset"] = unit_offset
        records = self._rows("die", filters, order_by=("ordinal",), operation="children_for_die")
        records = tuple(record for record in records if not record.get("is_null"))
        attributes = self._attributes_by_die(unit_offset, records)
        children = tuple(
            self._die_from_record(record, attributes.get(int(record.get("die_offset", 0)), ()))
            for record in records
        )
        self._children[die_offset] = children
        prefetch_children(self, children)
        prefetch_dies(self, children)
        return iter(children)

    def attribute_target(self, die_offset: int, attribute_name: str) -> int | None:
        unit_offset = self._die_unit_offsets.get(die_offset)
        cache_key = (unit_offset, die_offset, attribute_name)
        if cache_key in self._reference_targets:
            self.record_cache_hit()
            return self._reference_targets[cache_key]
        self.record_cache_miss()
        cached_die = self._dies.get(die_offset)
        if cached_die is not None:
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
        rows = self._rows(
            "reference",
            filters,
            columns=("target_offset",),
            limit=1,
            operation="attribute_target",
        )
        target = rows[0].get("target_offset") if rows else None
        result = _optional_int(target)
        self._reference_targets[cache_key] = result
        return result

    def line_program_for_unit(self, unit_offset: int) -> StoreLineProgram | None:
        cached = self._line_programs.get(unit_offset)
        if unit_offset in self._line_programs:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        program = build_line_program(
            self._rows(
                "line",
                {"unit_offset": unit_offset},
                order_by=("ordinal",),
                operation="line_program_for_unit",
            )
        )
        self._line_programs[unit_offset] = program
        return program

    @property
    def unit_count(self) -> int:
        return self._manifest_count("unit")

    @property
    def die_count(self) -> int:
        return self._manifest_count("die")

    @property
    def definition_name_count(self) -> int:
        if self._definition_name_count is None:
            rows = self._rows(
                "index",
                {"index_type": "definition"},
                columns=("name",),
                table_name=self._name_lookup_table,
                operation="definition_name_count",
            )
            self._definition_name_count = len(
                {row.get("name") for row in rows if isinstance(row.get("name"), str)}
            )
        return self._definition_name_count

    def as_dwarf_info(self) -> DwarfInfo:
        return self.dwarf_info

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
    ) -> tuple[dict[str, Any], ...]:
        query_options: dict[str, Any] = {
            "columns": columns,
            "order_by": order_by,
            "limit": limit,
        }
        if table_name is not None:
            query_options["table_name"] = table_name
        query_options["operation"] = operation
        rows = self._queries.family_rows(family, filters, **query_options)
        return tuple(restore_row(dict(row)) for row in rows)

    def _unit_from_record(self, record: dict[str, Any]) -> DorisCompilationUnit:
        unit_offset = int(record.get("unit_offset", 0))
        cached = self._units.get(unit_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        unit = DorisCompilationUnit(self, record)
        self._units[unit_offset] = unit
        return unit

    def _die_from_index_record(self, record: Mapping[str, Any]) -> DorisDie | None:
        unit_offset = _optional_int(record.get("unit_offset"))
        die_offset = _optional_int(record.get("die_offset"))
        if unit_offset is None or die_offset is None:
            return None
        cached = self._dies.get(die_offset)
        if cached is not None and self._die_unit_offsets.get(die_offset) == unit_offset:
            return cached
        rows = self._rows(
            "die",
            {"unit_offset": unit_offset, "die_offset": die_offset},
            limit=1,
            operation="hydrate_index_die",
        )
        return self._die_from_record(rows[0]) if rows else None

    def _die_from_record(
        self,
        record: Mapping[str, Any],
        attributes: Iterable[dict[str, Any]] | None = None,
    ) -> DorisDie:
        die_offset = int(record.get("die_offset", 0))
        cached = self._dies.get(die_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        unit_offset = int(record.get("unit_offset", 0))
        self._die_unit_offsets[die_offset] = unit_offset
        attribute_rows = (
            tuple(attributes)
            if attributes is not None
            else self._rows(
                "attribute",
                {"unit_offset": unit_offset, "die_offset": die_offset},
                columns=attribute_projection_columns(self),
                order_by=("ordinal",),
                operation="hydrate_die_attributes",
            )
        )
        data = DorisDieData(
            unit_offset=unit_offset,
            die_offset=die_offset,
            ordinal=int(record.get("ordinal", 0)),
            tag=_optional_text(record.get("tag")),
            abbrev_code=_optional_int(record.get("abbrev_code")),
            has_children=bool(record.get("has_children", False)),
            depth=int(record.get("depth", 0)),
            parent_offset=_optional_int(record.get("parent_offset")),
            is_null=bool(record.get("is_null", False)),
            attributes={str(row.get("name", "")): row for row in attribute_rows},
        )
        die = DorisDie(self, data)
        self._dies[die_offset] = die
        return die

    def _attributes_by_die(
        self,
        unit_offset: int | None,
        records: Iterable[Mapping[str, Any]],
    ) -> dict[int, tuple[dict[str, Any], ...]]:
        return attributes_by_die(self, unit_offset, records)

    def _manifest_count(self, family: str) -> int:
        return self.manifest.counts.get(family, 0)


def _validate_runtime_manifest(manifest: MaterializationManifest, path: Path) -> None:
    validate_schema_version(manifest, allow_incomplete=False)
    if manifest.status != "complete":
        raise ValueError(f"Analytical store is not complete: {path}")
    if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
        raise ValueError(f"Analytical store has partial DWARF parsing: {path}")


def _verify_source_binding(manifest: MaterializationManifest, source_path: Path | None) -> None:
    source = (source_path or Path(manifest.source_path)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Materialization source is unavailable: {source}")
    identity = SourceIdentityCatalog().identify(source)
    if identity.sha256 != manifest.source_identity.sha256:
        raise ValueError(f"Materialization source hash mismatch: {source}")

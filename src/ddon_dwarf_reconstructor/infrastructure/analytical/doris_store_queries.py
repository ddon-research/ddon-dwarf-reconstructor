"""Query operations mixed into the Doris-backed analytical store."""

from __future__ import annotations

from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.services.definition_selection import NestedTypeCounts
from .doris_hydration import hydrate_dies_by_keys, prime_child_tag_counts
from .doris_index import DorisDwarfIndex
from .doris_models import DorisDie
from .doris_store_helpers import definition_matches, optional_int, query_status, result
from .store_selection import prefer_cached_definition


class DorisStoreQueryMixin:
    """Definition, relationship, and result-shaping operations for the store."""

    def get_compilation_unit(self: Any, unit_offset: int) -> QueryResult:
        try:
            item = self.compilation_unit_by_offset(unit_offset)
        except KeyError:
            item = None
        return result(item, self.manifest_path, self.manifest.status)

    def get_die(self: Any, die_offset: int) -> QueryResult:
        return result(self.die_by_offset(die_offset), self.manifest_path, self.manifest.status)

    def find_definitions(
        self: Any,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        cache_key = (name, qualified_name, tags)
        cached = self._definition_query_cache.get(cache_key)
        if cached is not None:
            return cached
        filters: dict[str, object] = {"index_type": "definition", "name": name}
        if tags:
            filters["tag"] = tuple(sorted(tags))
        records = self._rows(
            "index",
            filters,
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
            limit=1001,
            table_name=self._name_lookup_table,
            operation="find_definitions",
        )
        hydrate_dies_by_keys(
            self,
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
            if (die := self._die_from_index_record(record)) is not None
            and definition_matches(die, qualified_name, tags)
        )
        prime_child_tag_counts(self, items)
        items = prefer_cached_definition(
            name, tuple(sorted(items, key=self._definition_sort_key)), self._selection_cache
        )
        query = QueryResult(
            query_status(bool(items), self.manifest.status), items, (str(self.manifest_path),)
        )
        self._definition_query_cache[cache_key] = query
        return query

    def find_primary_definition(
        self: Any,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        query = self.find_definitions(name, qualified_name=qualified_name, tags=tags)
        return QueryResult(query.status, query.items[:1], query.provenance, query.diagnostics)

    def find_method_implementation(self: Any, declaration_offset: int) -> QueryResult:
        records = self._rows(
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
            table_name=self._config.method_lookup_table,
        )
        for record in records:
            die = self._die_from_index_record(record)
            if die is not None:
                return result(die, self.manifest_path, self.manifest.status)
        return result(None, self.manifest_path, self.manifest.status)

    def children(self: Any, die_offset: int) -> QueryResult:
        items = tuple(self.children_for_die(die_offset))
        return QueryResult(
            query_status(bool(items), self.manifest.status), items, (str(self.manifest_path),)
        )

    def parent(self: Any, die_offset: int) -> QueryResult:
        die = self.die_by_offset(die_offset)
        return result(
            die.get_parent() if die is not None else None,
            self.manifest_path,
            self.manifest.status,
        )

    def references(self: Any, die_offset: int) -> QueryResult:
        unit_offset = self._die_unit_offsets.get(die_offset)
        filters: dict[str, object] = {"die_offset": die_offset}
        if unit_offset is not None:
            filters["unit_offset"] = unit_offset
        items = self._rows("reference", filters, order_by=("attribute_name", "relation"))
        return QueryResult(
            query_status(bool(items), self.manifest.status), items, (str(self.manifest_path),)
        )

    def child_tag_counts(self: Any, die_offset: int) -> NestedTypeCounts:
        cached = self._child_tag_counts.get(die_offset)
        if cached is not None:
            return cached
        rows = self._rows("die", {"parent_offset": die_offset}, columns=("tag", "is_null"))
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
        self._child_tag_counts[die_offset] = result_value
        return result_value

    def _definition_sort_key(self: Any, die: DorisDie) -> tuple[int, int, int, int]:
        candidate = DorisDwarfIndex._candidate("", die, self)
        return (-candidate.score, die.cu.cu_offset, die.offset, die.depth)

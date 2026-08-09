"""Query-port operations for the partition-pruned Parquet store."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from .jsonl_store import (
    StoreCompilationUnit,
    StoreDie,
    _definition_matches,
    _definition_sort_key,
    _query_status,
)
from .line_program import StoreLineProgram, build_line_program
from .parquet_layout import UNIT_BUCKET_SIZE
from .parquet_rows import restore_record
from .parquet_store_access import (
    _filter_expression,
    _ParquetStoreAccess,
    _read_table,
    _selected_columns,
)
from .parquet_store_helpers import (
    attributes_by_die as _attributes_by_die,
)
from .parquet_store_helpers import (
    child_tag_counts_from_rows as _child_tag_counts_from_rows,
)
from .parquet_store_helpers import (
    effective_filters as _effective_filters,
)
from .parquet_store_helpers import (
    index_die_key as _index_die_key,
)
from .parquet_store_helpers import (
    index_keys_by_bucket as _index_keys_by_bucket,
)
from .parquet_store_helpers import (
    is_zstd_scan_error as _is_zstd_scan_error,
)
from .parquet_store_helpers import (
    missing_index_keys as _missing_index_keys,
)
from .parquet_store_helpers import (
    optional_int as _optional_int,
)
from .parquet_store_helpers import (
    record_sort_key as _record_sort_key,
)
from .parquet_store_helpers import (
    result as _result,
)
from .parquet_store_helpers import (
    uncached_definition_offsets as _uncached_definition_offsets,
)
from .store_selection import prefer_cached_definition

_ATTRIBUTE_FALLBACK_BATCH_SIZE = 64


class ParquetStoreQueries(_ParquetStoreAccess):
    """Expose the analytical query-port operations over hydrated Parquet rows."""

    def line_program_for_unit(self, unit_offset: int) -> StoreLineProgram | None:
        """Reconstruct a CU line program through the typed line table."""
        return build_line_program(
            self._payload_rows({"record_type": "line", "unit_offset": unit_offset})
        )

    def get_compilation_unit(self, unit_offset: int) -> QueryResult:
        return _result(
            self.compilation_unit_by_offset_or_none(unit_offset),
            self.manifest_path,
            self.manifest.status,
        )

    def get_die(self, die_offset: int) -> QueryResult:
        return _result(self.die_by_offset(die_offset), self.manifest_path, self.manifest.status)

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        cache = getattr(self, "_definition_query_cache", None)
        if cache is None:
            cache = {}
            self._definition_query_cache = cache
        cache_key = (name, qualified_name, tags)
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        filters: dict[str, Any] = {
            "record_type": "index",
            "index_type": "definition",
            "name": name,
        }
        if tags:
            filters["tag"] = tuple(sorted(tags))
        records = sorted(
            self._payload_rows(filters),
            key=_record_sort_key,
        )
        items = tuple(
            die
            for die in self._dies_for_index_records(records)
            if _definition_matches(die, qualified_name, tags)
        )
        self._prime_child_tag_counts(items)
        items = prefer_cached_definition(
            name,
            tuple(sorted(items, key=_definition_sort_key)),
            getattr(self, "_selection_cache", None),
        )
        status = _query_status(bool(items), self.manifest.status)
        result = QueryResult(status, items, (str(self.manifest_path),))
        cache[cache_key] = result
        return result

    def find_primary_definition(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        cache = getattr(self, "_selection_cache", None)
        offset = (
            cache.get_symbol_offset(name)
            if cache is not None and qualified_name is None and tags is None
            else None
        )
        if isinstance(offset, int):
            records = self._payload_rows(
                {
                    "record_type": "index",
                    "index_type": "definition",
                    "name": name,
                    "die_offset": offset,
                }
            )
            for record in records:
                die = self._die_for_index_record(record)
                if die is not None and "DW_AT_declaration" not in die.attributes:
                    return _result(die, self.manifest_path, self.manifest.status)
        result = self.find_definitions(name, qualified_name=qualified_name, tags=tags)
        return QueryResult(
            result.status,
            result.items[:1],
            result.provenance,
            result.diagnostics,
        )

    def _prime_child_tag_counts(self, dies: Iterable[StoreDie]) -> None:
        """Hydrate definition-ranking child counts with one projected DIE scan."""
        cache = getattr(self, "_child_tag_counts", None)
        datasets = getattr(self, "_datasets", None)
        if not isinstance(cache, dict) or not isinstance(datasets, dict):
            return
        items = tuple(dies)
        offsets = _uncached_definition_offsets(items, cache)
        if not offsets:
            return
        grouped: dict[int, tuple[set[int], set[int]]] = {}
        for die in items:
            if die.offset not in offsets:
                continue
            unit_offset = getattr(getattr(die, "cu", None), "cu_offset", None)
            if not isinstance(unit_offset, int):
                continue
            unit_offsets, parent_offsets = grouped.setdefault(
                unit_offset // UNIT_BUCKET_SIZE, (set(), set())
            )
            unit_offsets.add(unit_offset)
            parent_offsets.add(die.offset)
        for unit_bucket, (unit_offsets, parent_offsets) in grouped.items():
            rows = self._rows(
                {
                    "record_type": "die",
                    "unit_offset": tuple(sorted(unit_offsets)),
                    "unit_bucket": unit_bucket,
                    "parent_offset": tuple(sorted(parent_offsets)),
                },
                columns=("parent_offset", "tag", "is_null"),
            )
            cache.update(_child_tag_counts_from_rows(rows, parent_offsets))

    def _dies_for_index_records(self, records: list[dict[str, Any]]) -> tuple[StoreDie, ...]:
        """Hydrate indexed DIEs with one batched DIE and attribute scan."""
        if not hasattr(self, "_die_cache"):
            return tuple(
                die for record in records if (die := self._die_for_index_record(record)) is not None
            )
        key_sequence = tuple(
            key for record in records if (key := _index_die_key(record)) is not None
        )
        keys = set(key_sequence)
        if not keys:
            return ()
        missing_keys = _missing_index_keys(keys, self._die_cache)
        self._hydrate_index_dies(keys, missing_keys)
        return self._cached_index_dies(key_sequence)

    def _hydrate_index_dies(
        self,
        keys: set[tuple[int, int]],
        missing_keys: tuple[tuple[int, int], ...],
    ) -> None:
        """Hydrate indexed DIEs with bucket-scoped attribute batches."""
        if not missing_keys:
            return
        die_rows = self._die_rows_by_bucket(missing_keys)
        attribute_rows = self._attribute_rows_by_bucket(missing_keys)
        attributes_by_key = _attributes_by_die(attribute_rows)
        for record in die_rows:
            key = _index_die_key(record)
            if key is not None and key in keys:
                self._die_from_record(record, attributes_by_key.get(key, ()))

    def _die_rows_by_bucket(
        self, missing_keys: tuple[tuple[int, int], ...]
    ) -> list[dict[str, Any]]:
        """Read indexed DIEs with the same CU partition pruning as attributes."""
        rows: list[dict[str, Any]] = []
        for unit_bucket, unit_offsets, die_offsets in _index_keys_by_bucket(missing_keys):
            rows.extend(
                self._payload_rows(
                    {
                        "record_type": "die",
                        "unit_offset": unit_offsets,
                        "unit_bucket": unit_bucket,
                        "die_offset": die_offsets,
                    }
                )
            )
        return rows

    def _attribute_rows_by_bucket(
        self, missing_keys: tuple[tuple[int, int], ...]
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for unit_bucket, unit_offsets, bucket_die_offsets in _index_keys_by_bucket(missing_keys):
            rows.extend(
                self._attribute_rows_for_bucket(
                    missing_keys, unit_bucket, unit_offsets, bucket_die_offsets
                )
            )
        return rows

    def _attribute_rows_for_bucket(
        self,
        missing_keys: tuple[tuple[int, int], ...],
        unit_bucket: int,
        unit_offsets: tuple[int, ...],
        die_offsets: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        filters = {
            "record_type": "attribute",
            "unit_offset": unit_offsets,
            "unit_bucket": unit_bucket,
            "die_offset": die_offsets,
        }
        try:
            return self._payload_rows(filters)
        except OSError as error:
            if not _is_zstd_scan_error(error):
                raise
            bucket_keys = tuple(
                key for key in missing_keys if key[0] // UNIT_BUCKET_SIZE == unit_bucket
            )
            try:
                return self._attribute_rows_by_unit(bucket_keys)
            except OSError as fallback_error:
                raise OSError(
                    "partition-scoped attribute hydration failed after CU fallback: "
                    f"{fallback_error}"
                ) from error

    def _cached_index_dies(self, keys: Iterable[tuple[int, int]]) -> tuple[StoreDie, ...]:
        return tuple(
            self._die_cache[die_offset]
            for _unit_offset, die_offset in keys
            if die_offset in self._die_cache
        )

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        records = sorted(
            self._payload_rows(
                {
                    "record_type": "index",
                    "index_type": "method_implementation",
                    "target_offset": declaration_offset,
                }
            ),
            key=_record_sort_key,
        )
        for record in records:
            if (
                _optional_int(record.get("die_offset")) is not None
                and record.get("resolution_status") == QueryStatus.COMPLETE.value
            ):
                die = self._die_for_index_record(record)
                if die is None:
                    continue
                return QueryResult(
                    _query_status(True, self.manifest.status),
                    (die,),
                    (str(self.manifest_path),),
                )
        return QueryResult(
            _query_status(False, self.manifest.status),
            (),
            (str(self.manifest_path),),
        )

    def children(self, die_offset: int) -> QueryResult:
        items = tuple(self.children_for_die(die_offset))
        status = _query_status(bool(items), self.manifest.status)
        return QueryResult(status, items, (str(self.manifest_path),))

    def parent(self, die_offset: int) -> QueryResult:
        die = self.die_by_offset(die_offset)
        parent = die.get_parent() if die is not None else None
        return _result(parent, self.manifest_path, self.manifest.status)

    def references(self, die_offset: int) -> QueryResult:
        items = tuple(
            self._payload_rows(
                self._die_scoped_filters("reference", die_offset, die_offset=die_offset)
            )
        )
        status = _query_status(bool(items), self.manifest.status)
        return QueryResult(status, items, (str(self.manifest_path),))

    def _count_records(self, record_type: str) -> int:
        cached = self._counts.get(record_type)
        if cached is None:
            dataset = self._datasets.get(record_type)
            cached = int(dataset.count_rows()) if dataset is not None else 0
            self._counts[record_type] = cached
        return cached

    def _payload_rows(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return [restore_record(row) for row in self._rows(filters)]

    def _attribute_rows_by_unit(self, keys: Iterable[tuple[int, int]]) -> list[dict[str, Any]]:
        grouped: dict[int, set[int]] = {}
        for unit_offset, die_offset in keys:
            grouped.setdefault(unit_offset, set()).add(die_offset)
        rows: list[dict[str, Any]] = []
        for unit_offset, die_offsets in sorted(grouped.items()):
            ordered_offsets = tuple(sorted(die_offsets))
            for start in range(0, len(ordered_offsets), _ATTRIBUTE_FALLBACK_BATCH_SIZE):
                batch = ordered_offsets[start : start + _ATTRIBUTE_FALLBACK_BATCH_SIZE]
                rows.extend(self._attribute_rows_batch(unit_offset, batch))
        return rows

    def _attribute_rows_batch(
        self, unit_offset: int, die_offsets: tuple[int, ...]
    ) -> list[dict[str, Any]]:
        filters = {
            "record_type": "attribute",
            "unit_offset": unit_offset,
            "unit_bucket": unit_offset // UNIT_BUCKET_SIZE,
            "die_offset": die_offsets,
        }
        try:
            return self._payload_rows(filters)
        except OSError as error:
            if not _is_zstd_scan_error(error) or len(die_offsets) == 1:
                raise
            midpoint = len(die_offsets) // 2
            return self._attribute_rows_batch(
                unit_offset, die_offsets[:midpoint]
            ) + self._attribute_rows_batch(unit_offset, die_offsets[midpoint:])

    def _rows(
        self,
        filters: dict[str, Any],
        columns: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        kind = filters.get("record_type")
        if not isinstance(kind, str):
            raise ValueError("Parquet queries must select one record family")
        dataset = self._datasets.get(kind)
        if dataset is None:
            return []
        available = set(dataset.schema.names)
        effective_filters = _effective_filters(
            filters, self.manifest.source_identity.sha256, available
        )
        expression = _filter_expression(self._dataset_module, effective_filters)
        selected = _selected_columns(dataset, columns, available)
        table = _read_table(dataset, expression, selected)
        return table.to_pylist()

    def compilation_unit_by_offset_or_none(self, unit_offset: int) -> StoreCompilationUnit | None:
        try:
            return self.compilation_unit_by_offset(unit_offset)
        except KeyError:
            return None

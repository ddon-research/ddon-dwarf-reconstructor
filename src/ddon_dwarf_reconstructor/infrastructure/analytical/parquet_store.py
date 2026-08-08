"""Predicate-backed Parquet query adapter for the analytical runtime."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import (
    DwarfRecordKind,
    MaterializationManifest,
    MaterializedUnit,
    QueryResult,
    QueryStatus,
)
from ...domain.services.definition_selection import NestedTypeCounts
from .jsonl_models import DieData
from .jsonl_store import (
    JsonlDwarfStore,
    StoreCompilationUnit,
    StoreDie,
    _definition_matches,
    _definition_sort_key,
    _MaterializedCache,
    _query_status,
)
from .line_program import StoreLineProgram, build_line_program
from .manifest import declared_parquet_files
from .optional import import_optional
from .parquet_layout import UNIT_BUCKET_SIZE, partitioning_for_layout
from .parquet_rows import restore_record
from .parquet_store_helpers import (
    attributes_by_die as _attributes_by_die,
)
from .parquet_store_helpers import (
    build_datasets as _build_datasets,
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
    is_multi_value as _is_multi_value,
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


class ParquetDwarfStore(JsonlDwarfStore):
    """Read only the Parquet rows needed by a query without loading JSONL."""

    def __init__(
        self,
        manifest_path: Path,
        manifest: MaterializationManifest,
        *,
        selection_cache: Any = None,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.manifest = manifest
        self.root = self.manifest_path.parent
        pyarrow = import_optional("pyarrow", "analytical")
        parquet = import_optional("pyarrow.dataset", "analytical")
        parquet_root = self.root / manifest.files["parquet"]
        family_dirs = {
            kind.value: parquet_root / kind.value
            for kind in DwarfRecordKind
            if kind is not DwarfRecordKind.MANIFEST
        }
        self._dataset_module = parquet
        layout = str(manifest.configuration.get("parquet_layout", "bucketed"))
        partitioning = partitioning_for_layout(pyarrow, parquet, layout)
        self._datasets = _build_datasets(
            parquet,
            family_dirs,
            parquet_root,
            partitioning,
            declared_parquet_files(self.manifest_path, manifest),
        )
        if not self._datasets:
            raise FileNotFoundError(f"No Parquet files found under {self.root / 'parquet'}")
        self._unit_cache: dict[int, StoreCompilationUnit] = {}
        self._die_cache: dict[int, StoreDie] = {}
        self._die_unit_offsets: dict[int, int] = {}
        self._unit_ranges: tuple[tuple[int, int], ...] | None = None
        self._children_cache: dict[int, tuple[StoreDie, ...]] = {}
        self._reference_targets: dict[tuple[int, str], int] = {}
        self._reference_units_loaded: set[int] = set()
        self._child_tag_counts: dict[int, NestedTypeCounts] = {}
        self._counts: dict[str, int] = {}
        self._definition_query_cache: dict[
            tuple[str, str | None, frozenset[str] | None], QueryResult
        ] = {}
        self._selection_cache = selection_cache
        self.dwarf_info = self._new_dwarf_info()
        self.persistent_cache = _MaterializedCache(self)

    def _new_dwarf_info(self) -> Any:
        from .jsonl_store import StoreDwarfInfo

        return StoreDwarfInfo(self)

    @property
    def unit_count(self) -> int:
        return self._count_records("unit")

    @property
    def die_count(self) -> int:
        return self._count_records("die")

    @property
    def definition_name_count(self) -> int:
        rows = self._rows(
            {"record_type": "index", "index_type": "definition"},
            columns=("name",),
        )
        return len({row.get("name") for row in rows if isinstance(row.get("name"), str)})

    def iter_dwarf_units(self) -> Iterable[StoreCompilationUnit]:
        rows = self._payload_rows({"record_type": "unit"})
        for record in sorted(rows, key=lambda item: int(item.get("unit_offset", 0))):
            yield self.compilation_unit_by_offset(int(record.get("unit_offset", 0)))

    def iter_compilation_units(self) -> Iterable[MaterializedUnit]:
        """Expose the typed query-port unit contract from Parquet rows."""
        rows = self._payload_rows({"record_type": "unit"})
        for record in sorted(rows, key=lambda item: int(item.get("unit_offset", 0))):
            header = record.get("header", {})
            yield MaterializedUnit(
                source_id=str(record.get("source_id", self.manifest.source_identity.sha256)),
                unit_offset=int(record.get("unit_offset", 0)),
                unit_length=_optional_int(record.get("unit_length")),
                header=header if isinstance(header, dict) else {},
                unit_type=record.get("unit_type")
                if isinstance(record.get("unit_type"), str)
                else None,
                parser_status=record.get("parser_status")
                if isinstance(record.get("parser_status"), str)
                else None,
                details=record.get("details"),
            )

    def compilation_unit_by_offset(self, unit_offset: int) -> StoreCompilationUnit:
        cached = self._unit_cache.get(unit_offset)
        if cached is not None:
            return cached
        rows = self._payload_rows({"record_type": "unit", "unit_offset": unit_offset})
        if not rows:
            raise KeyError(f"Compilation unit 0x{unit_offset:x} is not materialized")
        unit = StoreCompilationUnit(self, rows[0])
        self._unit_cache[unit_offset] = unit
        return unit

    def die_by_offset(self, die_offset: int | None) -> StoreDie | None:
        if die_offset is None:
            return None
        cached = self._die_cache.get(die_offset)
        if cached is not None:
            return cached
        filters: dict[str, Any] = {"record_type": "die", "die_offset": die_offset}
        unit_offset = self._unit_offset_for_die(die_offset)
        if unit_offset is not None:
            filters.update(
                {
                    "unit_offset": unit_offset,
                    "unit_bucket": unit_offset // UNIT_BUCKET_SIZE,
                }
            )
        rows = self._payload_rows(filters)
        if not rows:
            return None
        record = rows[0]
        return self._die_from_record(record)

    def _die_from_record(
        self,
        record: dict[str, Any],
        attributes: Iterable[dict[str, Any]] | None = None,
    ) -> StoreDie:
        """Hydrate one DIE with its CU partition predicate already known."""
        die_offset = int(record.get("die_offset", 0))
        cached = self._die_cache.get(die_offset)
        if cached is not None:
            return cached
        unit_offset = int(record.get("unit_offset", 0))
        self._die_unit_offsets[die_offset] = unit_offset
        attribute_rows = attributes
        if attribute_rows is None:
            attribute_rows = self._payload_rows(
                {
                    "record_type": "attribute",
                    "unit_offset": unit_offset,
                    "die_offset": die_offset,
                }
            )
        attribute_mapping = {
            str(attribute.get("name", "")): attribute for attribute in attribute_rows
        }
        data = DieData(
            unit_offset=unit_offset,
            die_offset=die_offset,
            ordinal=int(record.get("ordinal", 0)),
            tag=record.get("tag"),
            abbrev_code=record.get("abbrev_code"),
            has_children=bool(record.get("has_children", False)),
            depth=int(record.get("depth", 0)),
            parent_offset=record.get("parent_offset"),
            is_null=bool(record.get("is_null", False)),
            attributes=attribute_mapping,
        )
        die = StoreDie(self, data)
        self._die_cache[die_offset] = die
        return die

    def _unit_offset_for_die(self, die_offset: int) -> int | None:
        if die_offset in self._die_unit_offsets:
            return self._die_unit_offsets[die_offset]
        if self._unit_ranges is None:
            self._unit_ranges = self._load_unit_ranges()
        starts = [start for start, _end in self._unit_ranges]
        index = bisect_right(starts, die_offset) - 1
        if index < 0:
            return None
        unit_offset, unit_end = self._unit_ranges[index]
        if die_offset >= unit_end:
            return None
        self._die_unit_offsets[die_offset] = unit_offset
        return unit_offset

    def _load_unit_ranges(self) -> tuple[tuple[int, int], ...]:
        rows = self._rows(
            {"record_type": "unit"},
            columns=("unit_offset", "unit_length"),
        )
        starts = sorted(
            (
                row["unit_offset"],
                _optional_int(row.get("unit_length")),
            )
            for row in rows
            if isinstance(row.get("unit_offset"), int)
        )
        ranges: list[tuple[int, int]] = []
        for index, (unit_offset, unit_length) in enumerate(starts):
            next_offset = starts[index + 1][0] if index + 1 < len(starts) else None
            unit_end = unit_offset + unit_length + 4 if unit_length is not None else next_offset
            if unit_end is None:
                continue
            if next_offset is not None:
                unit_end = min(unit_end, next_offset)
            if unit_end > unit_offset:
                ranges.append((unit_offset, unit_end))
        return tuple(ranges)

    def _die_for_index_record(self, record: dict[str, Any]) -> StoreDie | None:
        """Resolve a derived index row to the lossless DIE row in its CU."""
        die_offset = _optional_int(record.get("die_offset"))
        unit_offset = _optional_int(record.get("unit_offset"))
        if die_offset is None or unit_offset is None:
            return None
        if not hasattr(self, "_die_cache"):
            return self.die_by_offset(die_offset)
        cached = self._die_cache.get(die_offset)
        if cached is not None:
            return cached
        die_rows = self._payload_rows(
            {"record_type": "die", "unit_offset": unit_offset, "die_offset": die_offset}
        )
        return self._die_from_record(die_rows[0]) if die_rows else None

    def dies_for_unit(self, unit_offset: int) -> Iterable[StoreDie]:
        rows = self._payload_rows({"record_type": "die", "unit_offset": unit_offset})
        attributes_by_key = self._attributes_by_die_records(rows)
        for record in sorted(rows, key=lambda item: int(item.get("ordinal", 0))):
            key = _index_die_key(record)
            attributes = attributes_by_key.get(key, ()) if key is not None else ()
            yield self._die_from_record(record, attributes)

    def children_for_die(self, die_offset: int) -> Iterable[StoreDie]:
        cached = self._children_cache.get(die_offset)
        if cached is not None:
            return iter(cached)
        filters = self._die_scoped_filters("die", die_offset, parent_offset=die_offset)
        rows = self._payload_rows(filters)
        children: list[StoreDie] = []
        attributes_by_key = self._attributes_by_die_records(rows)
        for record in sorted(rows, key=lambda item: int(item.get("ordinal", 0))):
            if record.get("is_null"):
                continue
            key = _index_die_key(record)
            attributes = attributes_by_key.get(key, ()) if key is not None else ()
            children.append(self._die_from_record(record, attributes))
        frozen = tuple(children)
        self._children_cache[die_offset] = frozen
        return iter(frozen)

    def child_tag_counts(self, die_offset: int) -> NestedTypeCounts:
        """Count ranking tags without hydrating every child attribute payload."""
        cached = self._child_tag_counts.get(die_offset)
        if cached is not None:
            return cached
        filters = self._die_scoped_filters("die", die_offset, parent_offset=die_offset)
        rows = self._rows(filters, columns=("tag", "is_null"))
        counts = {
            "DW_TAG_enumeration_type": 0,
            "DW_TAG_structure_type": 0,
            "DW_TAG_union_type": 0,
        }
        for row in rows:
            if row.get("is_null"):
                continue
            tag = row.get("tag")
            if tag in counts:
                counts[tag] += 1
        result = NestedTypeCounts(
            enums=counts["DW_TAG_enumeration_type"],
            structs=counts["DW_TAG_structure_type"],
            unions=counts["DW_TAG_union_type"],
        )
        self._child_tag_counts[die_offset] = result
        return result

    def attribute_target(self, die_offset: int, attribute_name: str) -> int | None:
        die = self._die_cache.get(die_offset)
        unit_offset = getattr(getattr(die, "cu", None), "cu_offset", None)
        if isinstance(unit_offset, int):
            self._load_reference_targets(unit_offset)
            return self._reference_targets.get((die_offset, attribute_name))
        filters = self._die_scoped_filters("reference", die_offset, die_offset=die_offset)
        for record in self._payload_rows(filters):
            if (
                record.get("relation") == "attribute_reference"
                and record.get("attribute_name") == attribute_name
            ):
                target = record.get("target_offset")
                return target if isinstance(target, int) else None
        return None

    def _attributes_by_die_records(
        self, records: Iterable[dict[str, Any]]
    ) -> dict[tuple[int, int], tuple[dict[str, Any], ...]]:
        keys = tuple(
            key
            for record in records
            if not record.get("is_null") and (key := _index_die_key(record)) is not None
        )
        if not keys:
            return {}
        missing = tuple(key for key in keys if key[1] not in self._die_cache)
        if not missing:
            return {}
        rows: list[dict[str, Any]] = []
        for unit_bucket, unit_offsets, die_offsets in _index_keys_by_bucket(missing):
            rows.extend(
                self._payload_rows(
                    {
                        "record_type": "attribute",
                        "unit_offset": unit_offsets,
                        "unit_bucket": unit_bucket,
                        "die_offset": die_offsets,
                    }
                )
            )
        grouped = _attributes_by_die(rows)
        return {
            (unit_offset, die_offset): attributes
            for (unit_offset, die_offset), attributes in grouped.items()
            if isinstance(unit_offset, int) and isinstance(die_offset, int)
        }

    def _load_reference_targets(self, unit_offset: int) -> None:
        if unit_offset in self._reference_units_loaded:
            return
        rows = self._payload_rows({"record_type": "reference", "unit_offset": unit_offset})
        for record in rows:
            if record.get("relation") != "attribute_reference":
                continue
            die_offset = _optional_int(record.get("die_offset"))
            attribute_name = record.get("attribute_name")
            target_offset = _optional_int(record.get("target_offset"))
            if (
                die_offset is not None
                and isinstance(attribute_name, str)
                and target_offset is not None
            ):
                self._reference_targets[(die_offset, attribute_name)] = target_offset
        self._reference_units_loaded.add(unit_offset)

    def _die_scoped_filters(
        self, record_type: str, lookup_die_offset: int, **filters: Any
    ) -> dict[str, Any]:
        result = {"record_type": record_type, **filters}
        die_cache = getattr(self, "_die_cache", {})
        die = die_cache.get(lookup_die_offset) if isinstance(die_cache, dict) else None
        unit_offset = getattr(getattr(die, "cu", None), "cu_offset", None)
        if isinstance(unit_offset, int):
            result["unit_offset"] = unit_offset
        return result

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


def _filter_expression(dataset_module: Any, filters: dict[str, Any]) -> Any:
    expression = None
    for name, value in filters.items():
        if name == "record_type":
            continue
        field = dataset_module.field(name)
        candidate = field.isin(list(value)) if _is_multi_value(value) else field == value
        expression = candidate if expression is None else expression & candidate
    return expression


def _selected_columns(
    dataset: Any, columns: tuple[str, ...] | None, available: set[str]
) -> list[str]:
    return [column for column in (columns or tuple(dataset.schema.names)) if column in available]


def _read_table(dataset: Any, expression: Any, selected: list[str]) -> Any:
    try:
        return dataset.to_table(filter=expression, columns=selected)
    except OSError as error:
        if not _is_zstd_scan_error(error):
            raise
        return dataset.to_table(filter=expression, columns=selected, use_threads=False)

"""Predicate-backed Parquet query adapter for the analytical runtime."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Self

from ...domain.models.analytical_dwarf import (
    DwarfRecordKind,
    MaterializationManifest,
    MaterializedUnit,
)
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import NestedTypeCounts
from ..artifacts import SourceIdentityCatalog
from .bounded_query_cache import BoundedQueryCache
from .jsonl_models import DieData
from .jsonl_views import StoreCompilationUnit, StoreDie, StoreDwarfInfo
from .line_program import StoreLineProgram, build_line_program
from .manifest import (
    declared_parquet_files,
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
    validate_manifest_files,
    validate_schema_version,
)
from .optional import import_optional
from .parquet_bounded_scan import read_bounded_rows as _read_bounded_rows
from .parquet_layout import UNIT_BUCKET_SIZE, partitioning_for_layout
from .parquet_rows import restore_record
from .parquet_store_helpers import (
    attributes_by_die as _attributes_by_die,
)
from .parquet_store_helpers import (
    build_datasets as _build_datasets,
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
    optional_int as _optional_int,
)


class _ParquetStoreAccess:
    """Load and hydrate the partition-pruned Parquet record families."""

    def __init__(
        self,
        manifest_path: Path,
        manifest: MaterializationManifest,
        *,
        selection_cache: SymbolCachePort | None = None,
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
        self._definition_query_cache = BoundedQueryCache()
        self._selection_cache = selection_cache
        self.dwarf_info = self._new_dwarf_info()

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        *,
        verify_source: bool = True,
        source_path: Path | None = None,
        allow_incomplete: bool = False,
        verify_artifacts: bool = False,
        selection_cache_path: Path | None = None,
        selection_source_fingerprint: dict[str, int | str] | None = None,
    ) -> Self:
        """Load a validated Parquet projection without JSONL inheritance."""
        manifest_path = manifest_path.resolve()
        manifest = load_manifest(manifest_path)
        validate_schema_version(manifest, allow_incomplete=allow_incomplete)
        if has_parser_diagnostics(manifest) and not allow_incomplete:
            raise ValueError(f"Analytical store has partial DWARF parsing: {manifest_path}")
        if has_unapplied_source_recovery(manifest) and not allow_incomplete:
            raise ValueError(f"Analytical store lacks source-bound DWARF recovery: {manifest_path}")
        if manifest.status != "complete" and not allow_incomplete:
            raise ValueError(f"Analytical store is not complete: {manifest_path}")
        validate_manifest_files(manifest_path, manifest, verify_hashes=verify_artifacts)
        if verify_source:
            _verify_parquet_source_binding(manifest, source_path)
        from .store_selection import load_selection_cache

        selection_cache = load_selection_cache(
            manifest,
            selection_cache_path,
            source_fingerprint=selection_source_fingerprint,
        )
        return cls(manifest_path, manifest, selection_cache=selection_cache)

    def _new_dwarf_info(self) -> Any:
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

    def as_dwarf_info(self) -> Any:
        """Return the generator-compatible Parquet DwarfInfo view."""
        return self.dwarf_info

    def line_program_for_unit(self, unit_offset: int) -> StoreLineProgram | None:
        return build_line_program(
            self._payload_rows({"record_type": "line", "unit_offset": unit_offset})
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
        unit_offset = die.cu.cu_offset if die is not None else None
        if unit_offset is not None:
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
        keys = _attribute_index_keys(records)
        missing = tuple(key for key in keys if key[1] not in self._die_cache)
        if not missing:
            return {}
        return _valid_attribute_groups(_attributes_by_die(self._attribute_rows_for_keys(missing)))

    def _attribute_rows_for_keys(self, keys: tuple[tuple[int, int], ...]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for unit_bucket, unit_offsets, die_offsets in _index_keys_by_bucket(keys):
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
        return rows

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
        die = self._die_cache.get(lookup_die_offset)
        unit_offset = die.cu.cu_offset if die is not None else None
        if unit_offset is not None:
            result["unit_offset"] = unit_offset
        return result

    def _count_records(self, record_type: str) -> int:
        cached = self._counts.get(record_type)
        if cached is None:
            dataset = self._datasets.get(record_type)
            cached = int(dataset.count_rows()) if dataset is not None else 0
            self._counts[record_type] = cached
        return cached

    def _payload_rows(
        self,
        filters: dict[str, Any],
        *,
        limit: int | None = None,
        order_key: Callable[[dict[str, Any]], tuple[int, ...]] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            restore_record(row) for row in self._rows(filters, limit=limit, order_key=order_key)
        ]

    def _rows(
        self,
        filters: dict[str, Any],
        columns: tuple[str, ...] | None = None,
        *,
        limit: int | None = None,
        order_key: Callable[[dict[str, Any]], tuple[int, ...]] | None = None,
    ) -> list[dict[str, Any]]:
        if limit is not None and limit < 1:
            raise ValueError("Parquet row limit must be positive")
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
        if limit is None:
            table = _read_table(dataset, expression, selected)
            return table.to_pylist()
        return _read_bounded_rows(
            dataset,
            expression,
            selected,
            limit=limit,
            order_key=order_key,
        )


def _attribute_index_keys(
    records: Iterable[dict[str, Any]],
) -> tuple[tuple[int, int], ...]:
    return tuple(
        key
        for record in records
        if not record.get("is_null") and (key := _index_die_key(record)) is not None
    )


def _valid_attribute_groups(
    grouped: dict[tuple[Any, Any], tuple[dict[str, Any], ...]],
) -> dict[tuple[int, int], tuple[dict[str, Any], ...]]:
    return {
        (unit_offset, die_offset): attributes
        for (unit_offset, die_offset), attributes in grouped.items()
        if isinstance(unit_offset, int) and isinstance(die_offset, int)
    }


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


def _verify_parquet_source_binding(
    manifest: MaterializationManifest,
    source_path: Path | None,
) -> None:
    source = (source_path or Path(manifest.source_path)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Materialization source is unavailable: {source}")
    identity = SourceIdentityCatalog().identify(source)
    if identity.sha256 != manifest.source_identity.sha256:
        raise ValueError(f"Materialization source hash mismatch: {source}")

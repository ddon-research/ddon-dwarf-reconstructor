"""Pure query-shaping helpers for the Parquet DWARF store adapter."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult
from ...domain.services.definition_selection import NestedTypeCounts
from .jsonl_views import StoreDie
from .materialized_selection import query_status as _query_status
from .parquet_layout import UNIT_BUCKET_SIZE


def build_datasets(
    parquet: Any,
    family_dirs: dict[str, Path],
    parquet_root: Path,
    partitioning: Any,
    configured_files: tuple[Path, ...] | None,
) -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for kind, family_dir in family_dirs.items():
        files = family_files(configured_files, parquet_root, kind)
        if configured_files is None:
            if family_dir.is_dir() and any(family_dir.rglob("part-*.parquet")):
                datasets[kind] = parquet.dataset(
                    str(family_dir), format="parquet", partitioning=partitioning
                )
        elif files:
            datasets[kind] = parquet.dataset(
                [str(path) for path in files],
                format="parquet",
                partitioning=partitioning,
                partition_base_dir=str(parquet_root),
            )
    return datasets


def family_files(
    configured_files: tuple[Path, ...] | None,
    parquet_root: Path,
    kind: str,
) -> tuple[Path, ...] | None:
    if configured_files is None:
        return None
    result: list[Path] = []
    for path in configured_files:
        try:
            relative = path.relative_to(parquet_root)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] == kind:
            result.append(path)
    return tuple(result)


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def uncached_definition_offsets(
    dies: Iterable[StoreDie], cache: dict[int, NestedTypeCounts]
) -> set[int]:
    return {die.offset for die in dies if isinstance(die.offset, int) and die.offset not in cache}


def child_tag_counts_from_rows(
    rows: Iterable[dict[str, Any]], offsets: set[int]
) -> dict[int, NestedTypeCounts]:
    counts = {offset: [0, 0, 0] for offset in offsets}
    for row in rows:
        if row.get("is_null"):
            continue
        parent_offset = optional_int(row.get("parent_offset"))
        index = nested_tag_index(row.get("tag"))
        values = counts.get(parent_offset) if parent_offset is not None else None
        if values is not None and index is not None:
            values[index] += 1
    return {
        offset: NestedTypeCounts(enums=values[0], structs=values[1], unions=values[2])
        for offset, values in counts.items()
    }


def nested_tag_index(tag: Any) -> int | None:
    return (
        {
            "DW_TAG_enumeration_type": 0,
            "DW_TAG_structure_type": 1,
            "DW_TAG_union_type": 2,
        }.get(tag)
        if isinstance(tag, str)
        else None
    )


def effective_filters(
    filters: dict[str, Any], source_id: str, available: set[str]
) -> dict[str, Any]:
    """Add source and derived partition predicates to a store query."""

    effective = dict(filters)
    effective.setdefault("source_id", source_id)
    unit_offset = effective.get("unit_offset")
    if isinstance(unit_offset, int) and "unit_bucket" in available:
        effective.setdefault("unit_bucket", unit_offset // UNIT_BUCKET_SIZE)
    return effective


def attributes_by_die(
    rows: Iterable[dict[str, Any]],
) -> dict[tuple[int | None, int | None], tuple[dict[str, Any], ...]]:
    grouped: dict[tuple[int | None, int | None], list[dict[str, Any]]] = {}
    for row in rows:
        key = (optional_int(row.get("unit_offset")), optional_int(row.get("die_offset")))
        grouped.setdefault(key, []).append(row)
    return {key: tuple(values) for key, values in grouped.items()}


def index_die_key(record: dict[str, Any]) -> tuple[int, int] | None:
    unit_offset = optional_int(record.get("unit_offset"))
    die_offset = optional_int(record.get("die_offset"))
    return (unit_offset, die_offset) if unit_offset is not None and die_offset is not None else None


def missing_index_keys(
    keys: Iterable[tuple[int, int]], cache: dict[int, StoreDie]
) -> tuple[tuple[int, int], ...]:
    return tuple(
        (unit_offset, die_offset) for unit_offset, die_offset in keys if die_offset not in cache
    )


def index_keys_by_bucket(
    keys: Iterable[tuple[int, int]],
) -> tuple[tuple[int, tuple[int, ...], tuple[int, ...]], ...]:
    grouped: dict[int, tuple[set[int], set[int]]] = {}
    for unit_offset, die_offset in keys:
        unit_offsets, die_offsets = grouped.setdefault(
            unit_offset // UNIT_BUCKET_SIZE, (set(), set())
        )
        unit_offsets.add(unit_offset)
        die_offsets.add(die_offset)
    return tuple(
        (
            unit_bucket,
            tuple(sorted(unit_offsets)),
            tuple(sorted(die_offsets)),
        )
        for unit_bucket, (unit_offsets, die_offsets) in sorted(grouped.items())
    )


def is_zstd_scan_error(error: OSError) -> bool:
    message = str(error)
    return "ZSTD decompression failed" in message or "Data corruption detected" in message


def is_multi_value(value: Any) -> bool:
    return isinstance(value, (tuple, list, set, frozenset))


def record_sort_key(record: dict[str, Any]) -> tuple[int, int, int]:
    return (
        optional_int(record.get("unit_offset")) or 0,
        optional_int(record.get("die_offset")) or 0,
        optional_int(record.get("ordinal")) or 0,
    )


def result(item: Any, manifest_path: Path, manifest_status: str = "complete") -> QueryResult:
    status = _query_status(item is not None, manifest_status)
    return QueryResult(status, (item,) if item is not None else (), (str(manifest_path),))

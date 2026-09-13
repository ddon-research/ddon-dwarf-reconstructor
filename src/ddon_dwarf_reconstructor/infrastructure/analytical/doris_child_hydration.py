"""Bounded child-frontier hydration helpers for the Doris serving adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from ...domain.services.definition_selection import NestedTypeCounts
from .doris_batch_rows import hydration_rows
from .doris_hydration_cache import (
    DieKey,
    cache_contains_key,
    child_tag_count_cache_set,
    children_cache_set,
    children_cached,
    die_key,
)
from .doris_models import DorisDie

_HYDRATION_BATCH_SIZE = 512
_COUNTED_CHILD_TAGS = (
    "DW_TAG_enumeration_type",
    "DW_TAG_structure_type",
    "DW_TAG_union_type",
)
_DIE_METADATA_COLUMNS = (
    "unit_offset",
    "die_offset",
    "ordinal",
    "tag",
    "abbrev_code",
    "has_children",
    "depth",
    "parent_offset",
    "is_null",
)


def prime_child_tag_counts(store: Any, dies: Iterable[DorisDie]) -> None:
    """Batch the child-tag counts used by definition ranking."""
    existing = getattr(store, "_child_tag_counts_by_key", None)
    if existing is None:
        existing = store._child_tag_counts
    keys = tuple(dict.fromkeys(die_key(die) for die in dies))
    missing = tuple(key for key in keys if not cache_contains_key(existing, key, key[1]))
    if store._hydration_scope == "unit":
        _prime_unit_child_tag_counts(store, missing)
        return
    offsets = tuple(sorted({die_offset for _unit_offset, die_offset in missing}))
    for batch in _batched(offsets):
        requested = tuple(key for key in missing if key[1] in batch)
        _prime_child_tag_batch(store, None, batch, requested_keys=requested)


def _prime_unit_child_tag_counts(store: Any, keys: Sequence[DieKey]) -> None:
    grouped: dict[int, set[int]] = defaultdict(set)
    for unit_offset, die_offset in keys:
        grouped[unit_offset].add(die_offset)
    for unit_offset, offsets in sorted(grouped.items()):
        for batch in _batched(tuple(sorted(offsets))):
            _prime_child_tag_batch(
                store,
                unit_offset,
                batch,
                requested_keys=tuple((unit_offset, offset) for offset in batch),
            )


def _prime_child_tag_batch(
    store: Any,
    unit_offset: int | None,
    batch: Sequence[int],
    *,
    requested_keys: Sequence[DieKey],
) -> None:
    counts = {key: _empty_child_tag_counts() for key in requested_keys}
    filters: dict[str, object] = {"parent_offset": batch}
    if store._hydration_scope == "unit" and unit_offset is not None:
        filters["unit_offset"] = unit_offset
    if store._child_tag_filter == "targeted":
        filters["tag"] = _COUNTED_CHILD_TAGS
    rows = hydration_rows(
        store,
        "die",
        filters,
        columns=("unit_offset", "parent_offset", "tag", "is_null"),
        operation="prefetch_child_tag_counts",
    )
    for row in rows:
        _record_child_tag_count(counts, row, unit_offset)
    for key, values in counts.items():
        child_tag_count_cache_set(store, key, _nested_type_counts(values))


def _empty_child_tag_counts() -> dict[str, int]:
    return dict.fromkeys(_COUNTED_CHILD_TAGS, 0)


def _nested_type_counts(values: Mapping[str, int]) -> NestedTypeCounts:
    return NestedTypeCounts(
        enums=values["DW_TAG_enumeration_type"],
        structs=values["DW_TAG_structure_type"],
        unions=values["DW_TAG_union_type"],
    )


def _record_child_tag_count(
    counts: dict[DieKey, dict[str, int]],
    row: Mapping[str, Any],
    unit_offset: int | None,
) -> None:
    row_unit = _as_int(row.get("unit_offset"))
    parent_offset = _as_int(row.get("parent_offset"))
    tag = row.get("tag")
    key = (row_unit if row_unit is not None else unit_offset, parent_offset)
    if key[0] is None or key not in counts or row.get("is_null") or tag not in counts[key]:
        return
    counts[key][tag] += 1


def prefetch_children(
    store: Any,
    parents: Iterable[DorisDie],
    *,
    hydrate_records: Callable[[Any, Iterable[Mapping[str, Any]]], tuple[DorisDie, ...]],
) -> None:
    """Prefetch one bounded child frontier for the supplied parent DIEs."""
    unique_parents = _unique_dies(parents)
    _cache_leaf_children(store, unique_parents)
    missing = tuple(
        die_key(die) for die in unique_parents if not children_cached(store, die_key(die))
    )
    if store._hydration_scope == "unit":
        _prefetch_unit_children(store, missing, hydrate_records)
        return
    offsets = tuple(sorted({die_offset for _unit_offset, die_offset in missing}))
    for batch in _batched(offsets):
        requested = tuple(key for key in missing if key[1] in batch)
        records = _child_records(store, batch)
        _cache_child_groups(
            store,
            batch,
            hydrate_records(store, records),
            requested_keys=requested,
        )


def _prefetch_unit_children(
    store: Any,
    keys: Sequence[DieKey],
    hydrate_records: Callable[[Any, Iterable[Mapping[str, Any]]], tuple[DorisDie, ...]],
) -> None:
    grouped: dict[int, list[int]] = defaultdict(list)
    for unit_offset, die_offset in keys:
        grouped[unit_offset].append(die_offset)
    for unit_offset, parent_offsets in sorted(grouped.items()):
        for batch in _batched(tuple(sorted(set(parent_offsets)))):
            records = _child_records(store, batch, unit_offset=unit_offset)
            _cache_child_groups(
                store,
                batch,
                hydrate_records(store, records),
                unit_offset=unit_offset,
            )


def _child_records(
    store: Any,
    parent_offsets: Sequence[int],
    *,
    unit_offset: int | None = None,
) -> tuple[dict[str, Any], ...]:
    filters: dict[str, object] = {"parent_offset": parent_offsets}
    if store._hydration_scope == "unit" and unit_offset is not None:
        filters["unit_offset"] = unit_offset
    return tuple(
        row
        for row in hydration_rows(
            store,
            "die",
            filters,
            columns=_DIE_METADATA_COLUMNS,
            order_by=("parent_offset", "ordinal"),
            operation="prefetch_children",
        )
        if not row.get("is_null")
    )


def _cache_leaf_children(store: Any, parents: Iterable[DorisDie]) -> None:
    for parent in parents:
        if not parent.has_children:
            children_cache_set(store, die_key(parent), ())


def _cache_child_groups(
    store: Any,
    parent_offsets: Sequence[int],
    children: Iterable[DorisDie],
    *,
    unit_offset: int | None = None,
    requested_keys: Sequence[DieKey] = (),
) -> None:
    grouped: dict[DieKey, list[DorisDie]] = defaultdict(list)
    for die in children:
        if die.parent_offset is not None:
            grouped[(die.cu.cu_offset, die.parent_offset)].append(die)
    keys = tuple(requested_keys)
    if not keys and unit_offset is not None:
        keys = tuple((unit_offset, parent_offset) for parent_offset in parent_offsets)
    if not keys:
        parent_set = set(parent_offsets)
        keys = tuple(key for key in grouped if key[1] in parent_set)
    for key in keys:
        matching = grouped.get(key, ())
        children_cache_set(store, key, tuple(sorted(matching, key=lambda die: die.ordinal)))


def _unique_dies(dies: Iterable[DorisDie]) -> tuple[DorisDie, ...]:
    result: list[DorisDie] = []
    seen: set[DieKey] = set()
    for die in dies:
        key = die_key(die)
        if key not in seen:
            seen.add(key)
            result.append(die)
    return tuple(result)


def _batched(values: Sequence[int]) -> Iterable[tuple[int, ...]]:
    for start in range(0, len(values), _HYDRATION_BATCH_SIZE):
        yield tuple(values[start : start + _HYDRATION_BATCH_SIZE])


def _as_int(value: object) -> int | None:
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


__all__ = ["prefetch_children", "prime_child_tag_counts"]

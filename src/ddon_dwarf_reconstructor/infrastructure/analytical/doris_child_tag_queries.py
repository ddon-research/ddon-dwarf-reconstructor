"""Source/CU-aware child-tag count cache operations for Doris queries."""

from __future__ import annotations

from typing import Any

from ...domain.services.definition_selection import NestedTypeCounts
from .doris_batch_rows import hydration_rows


def child_tag_count_unit(store: Any, die_offset: int, unit_offset: int | None) -> int | None:
    if unit_offset is not None:
        return unit_offset
    return store._die_unit_offsets.get(die_offset)


def cached_child_tag_counts(
    store: Any, die_offset: int, unit_offset: int | None
) -> NestedTypeCounts | None:
    exact = getattr(store, "_child_tag_counts_by_key", None)
    if exact is not None and unit_offset is not None:
        cached = exact.get((unit_offset, die_offset))
        if cached is not None:
            return cached
    cached = store._child_tag_counts.get(die_offset)
    known_unit = store._die_unit_offsets.get(die_offset)
    if cached is not None and unit_offset is not None and known_unit != unit_offset:
        return None
    return cached


def load_child_tag_counts(store: Any, die_offset: int, unit_offset: int | None) -> NestedTypeCounts:
    filters: dict[str, object] = {"parent_offset": die_offset}
    if unit_offset is not None:
        filters["unit_offset"] = unit_offset
    rows = hydration_rows(store, "die", filters, columns=("tag", "is_null"))
    counts = {"DW_TAG_enumeration_type": 0, "DW_TAG_structure_type": 0, "DW_TAG_union_type": 0}
    for row in rows:
        tag = row.get("tag")
        if not row.get("is_null") and tag in counts:
            counts[tag] += 1
    return NestedTypeCounts(
        enums=counts["DW_TAG_enumeration_type"],
        structs=counts["DW_TAG_structure_type"],
        unions=counts["DW_TAG_union_type"],
    )


def cache_child_tag_counts(
    store: Any,
    die_offset: int,
    unit_offset: int | None,
    counts: NestedTypeCounts,
) -> None:
    exact = getattr(store, "_child_tag_counts_by_key", None)
    if exact is not None and unit_offset is not None:
        exact[(unit_offset, die_offset)] = counts
    if die_offset not in store._child_tag_counts:
        store._child_tag_counts[die_offset] = counts


__all__ = [
    "cache_child_tag_counts",
    "cached_child_tag_counts",
    "child_tag_count_unit",
    "load_child_tag_counts",
]

"""Bounded batch hydration helpers for the Doris serving adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol

from ...domain.services.definition_selection import NestedTypeCounts
from .bounded_query_cache import BoundedQueryCache
from .doris_batch_rows import hydration_rows
from .doris_child_hydration import prefetch_children as _prefetch_children
from .doris_child_hydration import prime_child_tag_counts
from .doris_hydration_cache import (
    DieKey,
)
from .doris_hydration_cache import (
    cached_die as _cached_die,
)
from .doris_hydration_cache import (
    die_key as _die_key,
)
from .doris_models import DorisCompilationUnit, DorisDie
from .doris_reference_hydration import (
    cached_reference_target_keys as _cached_reference_target_keys,
)
from .doris_reference_hydration import (
    load_reference_targets as _load_reference_targets,
)
from .doris_reference_hydration import (
    prefetch_references,
)
from .doris_reference_hydration import (
    reference_keys as _reference_keys,
)

__all__ = ["prefetch_children", "prime_child_tag_counts"]

HYDRATION_BATCH_SIZE = 512
_PREFETCH_DEPTH = 4
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
_SERVING_ATTRIBUTE_COLUMNS = (
    "unit_offset",
    "die_offset",
    "ordinal",
    "record_type",
    "name",
    "form",
    "value_offset",
    "indirection_length",
    "decoded_value_kind",
    "decoded_value_bool",
    "decoded_value_int",
    "decoded_value_uint",
    "decoded_value_float",
    "decoded_value_text",
    "decoded_value_binary",
    "decoded_value_json",
    "decoded_value_path",
    "decoded_value_sha256",
    "decoded_value_size",
)


class _DorisHydrationStore(Protocol):
    """Private store surface used by the bounded hydration functions."""

    _dies: BoundedQueryCache[int, DorisDie]
    _dies_by_key: BoundedQueryCache[DieKey, DorisDie]
    _die_unit_offsets: BoundedQueryCache[int, int]
    _units: BoundedQueryCache[int, DorisCompilationUnit]
    _children: BoundedQueryCache[int, tuple[DorisDie, ...]]
    _children_by_key: BoundedQueryCache[DieKey, tuple[DorisDie, ...]]
    _child_tag_counts: BoundedQueryCache[int, NestedTypeCounts]
    _child_tag_counts_by_key: BoundedQueryCache[DieKey, NestedTypeCounts]
    _reference_targets: BoundedQueryCache[tuple[int | None, int, str], int | None]
    _reference_loaded: set[tuple[int, int]]
    _reference_dies: BoundedQueryCache[int, None]
    _reference_dies_by_key: BoundedQueryCache[DieKey, None]
    _reference_prefetch: str
    _attribute_projection: str
    _child_tag_filter: str
    _hydration_scope: str

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

    def _unit_from_record(self, record: dict[str, Any]) -> DorisCompilationUnit: ...

    def _die_from_record(
        self,
        record: Mapping[str, Any],
        attributes: Iterable[dict[str, Any]] | None = None,
    ) -> DorisDie: ...


def batched(values: Sequence[int], size: int = HYDRATION_BATCH_SIZE) -> Iterable[tuple[int, ...]]:
    """Yield deterministic bounded batches and reject invalid batch sizes."""
    if size < 1:
        raise ValueError("batch size must be positive")
    for start in range(0, len(values), size):
        yield tuple(values[start : start + size])


def attributes_by_die(
    store: _DorisHydrationStore,
    unit_offset: int | None,
    records: Iterable[Mapping[str, Any]],
) -> dict[int, tuple[dict[str, Any], ...]]:
    """Read attributes for a direct child set in source/unit-bound batches."""
    offsets = tuple(
        int(record["die_offset"])
        for record in records
        if not record.get("is_null") and record.get("die_offset") is not None
    )
    if not offsets or unit_offset is None:
        return {}
    columns = attribute_projection_columns(store)
    rows: list[dict[str, Any]] = []
    for batch in batched(offsets):
        rows.extend(
            hydration_rows(
                store,
                "attribute",
                {"unit_offset": unit_offset, "die_offset": batch},
                columns=columns,
                order_by=("die_offset", "ordinal"),
                operation="hydrate_attributes_for_children",
            )
        )
    return _group_attributes(rows)


def hydrate_dies_by_keys(
    store: _DorisHydrationStore,
    keys: Iterable[tuple[int, int]],
) -> tuple[DorisDie, ...]:
    """Hydrate known ``(unit_offset, die_offset)`` keys with bounded set queries."""
    normalized = tuple(dict.fromkeys(keys))
    missing = tuple(key for key in normalized if _cached_die(store, key) is None)
    grouped: dict[int | None, list[int]] = defaultdict(list)
    for unit, die in missing:
        group = unit if store._hydration_scope == "unit" else None
        grouped[group].append(die)
    for unit, offsets in sorted(grouped.items(), key=str):
        _hydrate_offsets(store, tuple(offsets), unit_offset=unit)
    return tuple(cached for key in normalized if (cached := _cached_die(store, key)) is not None)


def hydrate_dies_by_offsets(
    store: _DorisHydrationStore,
    offsets: Iterable[int],
) -> tuple[DorisDie, ...]:
    """Hydrate a bounded global-offset frontier in deterministic batches.

    Callers with known compilation-unit offsets should prefer
    :func:`hydrate_dies_by_keys`, which can add the stronger unit predicate.
    """
    normalized = tuple(sorted(set(offsets)))
    if not normalized:
        return ()
    _hydrate_offsets(store, normalized)
    # Return the complete requested frontier, including objects that were
    # already cached before this batch.  The dependency walker uses this
    # result to classify every prefetched offset without falling back to one
    # ``get_die_by_offset`` call for cache hits.
    return tuple(die for offset in normalized if (die := store._dies.get(offset)) is not None)


def prefetch_dies(store: _DorisHydrationStore, dies: Iterable[DorisDie]) -> None:
    """Prefetch reference targets and parents for one direct-child frontier.

    The parser remains lazy: only references exposed by the current frontier are
    followed, and each SQL request is capped at 512 DIE keys. The bounded depth
    covers common qualifier/typedef chains without turning one lookup into a CU
    scan.
    """
    frontier = _unique_dies(store, dies)
    for _ in range(_PREFETCH_DEPTH):
        frontier = _next_prefetch_frontier(store, frontier)
        if not frontier:
            return


def prefetch_children(store: _DorisHydrationStore, parents: Iterable[DorisDie]) -> None:
    """Prefetch children through the canonical DIE record hydrator."""
    _prefetch_children(store, parents, hydrate_records=_hydrate_die_records)


def _next_prefetch_frontier(
    store: _DorisHydrationStore,
    frontier: tuple[DorisDie, ...],
) -> tuple[DorisDie, ...]:
    reference_keys = _reference_keys(store, frontier)
    targets = _load_reference_targets(store, reference_keys) if reference_keys else ()
    keys = set(targets)
    keys.update(_cached_reference_target_keys(store, frontier))
    keys.update(
        (die.cu.cu_offset, die.parent_offset) for die in frontier if die.parent_offset is not None
    )
    if not keys:
        return ()
    next_frontier = hydrate_dies_by_keys(store, tuple(sorted(keys)))
    if next_frontier:
        return next_frontier
    return tuple(cached for key in sorted(keys) if (cached := _cached_die(store, key)) is not None)


def _hydrate_offsets(
    store: _DorisHydrationStore,
    offsets: Sequence[int],
    *,
    unit_offset: int | None = None,
) -> tuple[DorisDie, ...]:
    unique_offsets = tuple(
        dict.fromkeys(offset for offset in offsets if not _is_hydrated(store, offset, unit_offset))
    )
    hydrated: list[DorisDie] = []
    for batch in batched(unique_offsets):
        config = getattr(store, "_config", None)
        lookup_table = getattr(config, "die_lookup_table", None)
        filters: dict[str, object] = {"die_offset": batch}
        if store._hydration_scope == "unit" and unit_offset is not None:
            filters["unit_offset"] = unit_offset
        die_rows = hydration_rows(
            store,
            "die",
            filters,
            columns=_DIE_METADATA_COLUMNS,
            order_by=("unit_offset", "ordinal"),
            table_name=lookup_table,
            operation="hydrate_dies_by_offset",
        )
        hydrated.extend(_hydrate_die_records(store, die_rows))
    return _unique_dies(store, hydrated)


def _is_hydrated(
    store: _DorisHydrationStore,
    offset: int,
    unit_offset: int | None,
) -> bool:
    """Return whether an offset already has a source-compatible DIE object."""
    if unit_offset is None:
        return store._dies.get(offset) is not None
    return _cached_die(store, (unit_offset, offset)) is not None


def _hydrate_die_records(
    store: _DorisHydrationStore,
    records: Iterable[Mapping[str, Any]],
) -> tuple[DorisDie, ...]:
    """Hydrate already-selected DIE rows and their attributes in bounded batches."""
    rows = tuple(records)
    if not rows:
        return ()
    _hydrate_units(store, _unit_offsets(rows))
    attributes = _attributes_for_die_offsets(store, rows)
    result = _unique_dies(
        store,
        (_hydrate_die_record(store, row, attributes) for row in rows),
    )
    if store._reference_prefetch == "eager":
        prefetch_references(store, result)
    return result


def _unit_offsets(records: Iterable[Mapping[str, Any]]) -> tuple[int, ...]:
    return tuple(
        sorted({int(row["unit_offset"]) for row in records if row.get("unit_offset") is not None})
    )


def _die_offsets(records: Iterable[Mapping[str, Any]]) -> tuple[int, ...]:
    return tuple(int(row["die_offset"]) for row in records if row.get("die_offset") is not None)


def _attributes_for_die_offsets(
    store: _DorisHydrationStore,
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[int, int], tuple[dict[str, Any], ...]]:
    attributes: dict[tuple[int, int], tuple[dict[str, Any], ...]] = {}
    columns = attribute_projection_columns(store)
    keys = _attribute_keys(records)
    groups = _group_keys_by_unit(store, keys)
    for unit_offset, die_offsets in groups:
        for batch in batched(die_offsets):
            filters: dict[str, object] = {"die_offset": batch}
            if store._hydration_scope == "unit" and unit_offset is not None:
                filters["unit_offset"] = unit_offset
            attributes.update(
                _group_attributes_by_key(
                    hydration_rows(
                        store,
                        "attribute",
                        filters,
                        columns=columns,
                        order_by=("unit_offset", "die_offset", "ordinal"),
                        operation="hydrate_attributes_by_die",
                    )
                )
            )
    return attributes


def _attribute_keys(records: Iterable[Mapping[str, Any]]) -> tuple[tuple[int, int], ...]:
    return tuple(
        (int(row["unit_offset"]), int(row["die_offset"]))
        for row in records
        if row.get("unit_offset") is not None and row.get("die_offset") is not None
    )


def _group_keys_by_unit(
    store: _DorisHydrationStore,
    keys: Iterable[tuple[int, int]],
) -> tuple[tuple[int | None, tuple[int, ...]], ...]:
    grouped: dict[int | None, set[int]] = defaultdict(set)
    for unit_offset, die_offset in keys:
        group = unit_offset if store._hydration_scope == "unit" else None
        grouped[group].add(die_offset)
    return tuple(
        (unit, tuple(sorted(offsets))) for unit, offsets in sorted(grouped.items(), key=str)
    )


def attribute_projection_columns(store: _DorisHydrationStore) -> tuple[str, ...]:
    """Return generator-only attribute columns, or empty for the lossless query."""
    return _SERVING_ATTRIBUTE_COLUMNS if store._attribute_projection == "serving" else ()


def _hydrate_die_record(
    store: _DorisHydrationStore,
    row: Mapping[str, Any],
    attributes: Mapping[tuple[int, int], tuple[dict[str, Any], ...]],
) -> DorisDie:
    unit_offset = _as_int(row.get("unit_offset"))
    die_offset = _as_int(row.get("die_offset"))
    if unit_offset is None or die_offset is None:
        raise ValueError("DIE hydration row lacks source-bound offsets")
    cached = _cached_die(store, (unit_offset, die_offset))
    if cached is not None:
        return cached
    return store._die_from_record(row, attributes.get((unit_offset, die_offset), ()))


def _hydrate_units(store: _DorisHydrationStore, offsets: Sequence[int]) -> None:
    missing = tuple(offset for offset in offsets if offset not in store._units)
    for batch in batched(missing):
        for row in hydration_rows(
            store,
            "unit",
            {"unit_offset": batch},
            order_by=("unit_offset",),
            operation="hydrate_units",
        ):
            store._unit_from_record(row)


def _group_attributes(rows: Iterable[dict[str, Any]]) -> dict[int, tuple[dict[str, Any], ...]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        die_offset = _as_int(row.get("die_offset"))
        if die_offset is not None:
            grouped[die_offset].append(row)
    return {offset: tuple(values) for offset, values in grouped.items()}


def _group_attributes_by_key(
    rows: Iterable[dict[str, Any]],
) -> dict[tuple[int, int], tuple[dict[str, Any], ...]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        unit_offset = _as_int(row.get("unit_offset"))
        die_offset = _as_int(row.get("die_offset"))
        if unit_offset is not None and die_offset is not None:
            grouped[(unit_offset, die_offset)].append(row)
    return {key: tuple(values) for key, values in grouped.items()}


def _unique_dies(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> tuple[DorisDie, ...]:
    result: list[DorisDie] = []
    seen: set[DieKey] = set()
    for die in dies:
        key = _die_key(die)
        if key not in seen:
            seen.add(key)
            result.append(die)
    return tuple(result)


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

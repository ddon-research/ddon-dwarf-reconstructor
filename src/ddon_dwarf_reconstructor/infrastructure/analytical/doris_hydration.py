"""Bounded batch hydration helpers for the Doris serving adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol

from ...domain.services.definition_selection import NestedTypeCounts
from .doris_models import DorisCompilationUnit, DorisDie

HYDRATION_BATCH_SIZE = 512
_PREFETCH_DEPTH = 4
_REFERENCE_NAMES = frozenset(
    {
        "DW_AT_type",
        "DW_AT_specification",
        "DW_AT_abstract_origin",
        "DW_AT_containing_type",
        "DW_AT_import",
        "DW_AT_signature",
    }
)
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

    _dies: dict[int, DorisDie]
    _die_unit_offsets: dict[int, int]
    _units: dict[int, DorisCompilationUnit]
    _children: dict[int, tuple[DorisDie, ...]]
    _child_tag_counts: dict[int, NestedTypeCounts]
    _reference_targets: dict[tuple[int | None, int, str], int | None]
    _reference_loaded: set[tuple[int, int]]
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
            store._rows(
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
    missing = tuple(
        (unit, die)
        for unit, die in normalized
        if store._die_unit_offsets.get(die) != unit or die not in store._dies
    )
    if missing:
        _hydrate_offsets(store, tuple(die for _unit, die in missing))
    return tuple(
        store._dies[die]
        for unit, die in normalized
        if store._die_unit_offsets.get(die) == unit and die in store._dies
    )


def prime_child_tag_counts(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> None:
    """Batch the child-tag counts used by definition ranking."""
    groups = _group_die_offsets_by_unit(store, dies, store._child_tag_counts)
    for unit_offset, offsets in groups:
        for batch in batched(offsets):
            _prime_child_tag_batch(store, unit_offset, batch)


def _prime_child_tag_batch(
    store: _DorisHydrationStore,
    unit_offset: int | None,
    batch: Sequence[int],
) -> None:
    counts = {
        offset: {
            "DW_TAG_enumeration_type": 0,
            "DW_TAG_structure_type": 0,
            "DW_TAG_union_type": 0,
        }
        for offset in batch
    }
    filters: dict[str, object] = {"parent_offset": batch}
    if store._hydration_scope == "unit" and unit_offset is not None:
        filters["unit_offset"] = unit_offset
    if store._child_tag_filter == "targeted":
        filters["tag"] = _COUNTED_CHILD_TAGS
    for row in store._rows(
        "die",
        filters,
        columns=("parent_offset", "tag", "is_null"),
        operation="prefetch_child_tag_counts",
    ):
        _record_child_tag_count(counts, row)
    for offset, values in counts.items():
        store._child_tag_counts[offset] = NestedTypeCounts(
            enums=values["DW_TAG_enumeration_type"],
            structs=values["DW_TAG_structure_type"],
            unions=values["DW_TAG_union_type"],
        )


def _record_child_tag_count(counts: dict[int, dict[str, int]], row: Mapping[str, Any]) -> None:
    parent_offset = _as_int(row.get("parent_offset"))
    tag = row.get("tag")
    if parent_offset not in counts or row.get("is_null") or tag not in counts[parent_offset]:
        return
    counts[parent_offset][tag] += 1


def _group_die_offsets_by_unit(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
    existing: Mapping[int, object],
) -> tuple[tuple[int | None, tuple[int, ...]], ...]:
    grouped: dict[int | None, set[int]] = defaultdict(set)
    for die in dies:
        if die.offset in existing:
            continue
        unit_offset = store._die_unit_offsets.get(die.offset, die.cu.cu_offset)
        key = unit_offset if store._hydration_scope == "unit" else None
        grouped[key].add(die.offset)
    return tuple(
        (unit, tuple(sorted(offsets))) for unit, offsets in sorted(grouped.items(), key=str)
    )


def prefetch_dies(store: _DorisHydrationStore, dies: Iterable[DorisDie]) -> None:
    """Prefetch reference targets and parents for one direct-child frontier.

    The parser remains lazy: only references exposed by the current frontier are
    followed, and each SQL request is capped at 512 DIE keys. The bounded depth
    covers common qualifier/typedef chains without turning one lookup into a CU
    scan.
    """
    frontier = _unique_dies(store, dies)
    for depth in range(_PREFETCH_DEPTH):
        reference_keys = _reference_keys(store, frontier)
        if len(reference_keys) < 2:
            return
        targets = _load_reference_targets(store, reference_keys)
        offsets = set(targets)
        offsets.update(die.parent_offset for die in frontier if die.parent_offset is not None)
        if not offsets:
            return
        next_frontier = _hydrate_offsets(store, tuple(sorted(offsets)))
        if not next_frontier:
            return
        frontier = next_frontier
        if depth == _PREFETCH_DEPTH - 1:
            return


def prefetch_references(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
    *,
    max_keys: int = HYDRATION_BATCH_SIZE,
) -> None:
    """Load a bounded reference frontier for already-hydrated DIEs."""
    if max_keys < 1:
        raise ValueError("maximum reference batch must be positive")
    keys = _reference_keys(store, dies)
    if len(keys) < 2:
        return
    _load_reference_targets(store, keys[:max_keys])


def reference_candidates(
    store: _DorisHydrationStore,
    current: DorisDie,
) -> Iterable[DorisDie]:
    """Yield the current DIE followed by the newest cached candidates."""
    yield current
    for die in reversed(tuple(store._dies.values())):
        if die.offset != current.offset:
            yield die


def prefetch_children(store: _DorisHydrationStore, parents: Iterable[DorisDie]) -> None:
    """Prefetch one bounded child frontier for the supplied parent DIEs."""
    unique_parents = _unique_dies(store, parents)
    _cache_leaf_children(store, unique_parents)
    parent_offsets = tuple(
        sorted({die.offset for die in unique_parents if die.offset not in store._children})
    )
    if not parent_offsets:
        return
    for batch in batched(parent_offsets):
        _cache_child_groups(store, batch, _hydrate_die_records(store, _child_records(store, batch)))


def _child_records(
    store: _DorisHydrationStore,
    parent_offsets: Sequence[int],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        row
        for row in store._rows(
            "die",
            {"parent_offset": parent_offsets},
            columns=_DIE_METADATA_COLUMNS,
            order_by=("parent_offset", "ordinal"),
            operation="prefetch_children",
        )
        if not row.get("is_null")
    )


def _cache_leaf_children(
    store: _DorisHydrationStore,
    parents: Iterable[DorisDie],
) -> None:
    for parent in parents:
        if not parent.has_children:
            store._children[parent.offset] = ()


def _cache_child_groups(
    store: _DorisHydrationStore,
    parent_offsets: Sequence[int],
    children: Iterable[DorisDie],
) -> None:
    grouped: dict[int, list[DorisDie]] = defaultdict(list)
    for die in children:
        if die.parent_offset is not None:
            grouped[die.parent_offset].append(die)
    for parent_offset in parent_offsets:
        store._children[parent_offset] = tuple(
            sorted(grouped.get(parent_offset, ()), key=lambda die: die.ordinal)
        )


def _hydrate_offsets(
    store: _DorisHydrationStore,
    offsets: Sequence[int],
) -> tuple[DorisDie, ...]:
    unique_offsets = tuple(dict.fromkeys(offsets))
    hydrated: list[DorisDie] = []
    for batch in batched(unique_offsets):
        die_rows = store._rows(
            "die",
            {"die_offset": batch},
            columns=_DIE_METADATA_COLUMNS,
            order_by=("unit_offset", "ordinal"),
            operation="hydrate_dies_by_offset",
        )
        hydrated.extend(_hydrate_die_records(store, die_rows))
    return _unique_dies(store, hydrated)


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
                    store._rows(
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
        key = unit_offset if store._hydration_scope == "unit" else None
        grouped[key].add(die_offset)
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
    if store._die_unit_offsets.get(die_offset) == unit_offset and die_offset in store._dies:
        return store._dies[die_offset]
    return store._die_from_record(row, attributes.get((unit_offset, die_offset), ()))


def _hydrate_units(store: _DorisHydrationStore, offsets: Sequence[int]) -> None:
    missing = tuple(offset for offset in offsets if offset not in store._units)
    for batch in batched(missing):
        for row in store._rows(
            "unit",
            {"unit_offset": batch},
            order_by=("unit_offset",),
            operation="hydrate_units",
        ):
            store._unit_from_record(row)


def _reference_keys(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> tuple[tuple[int, int], ...]:
    loaded = store._reference_loaded
    result: list[tuple[int, int]] = []
    for die in dies:
        unit_offset = store._die_unit_offsets.get(die.offset)
        if unit_offset is None:
            unit_offset = die.cu.cu_offset
        key = (unit_offset, die.offset)
        if key in loaded or not _has_reference_attribute(die):
            continue
        result.append(key)
    return tuple(dict.fromkeys(result))


def _load_reference_targets(
    store: _DorisHydrationStore,
    keys: Sequence[tuple[int, int]],
) -> tuple[int, ...]:
    targets: set[int] = set()
    target_cache, loaded = _reference_caches(store)
    wanted = set(keys)
    for unit_offset, offsets in _group_keys_by_unit(store, keys):
        for batch in batched(offsets):
            filters: dict[str, object] = {
                "die_offset": batch,
                "relation": "attribute_reference",
            }
            if store._hydration_scope == "unit" and unit_offset is not None:
                filters["unit_offset"] = unit_offset
            rows = store._rows(
                "reference",
                filters,
                columns=(
                    "unit_offset",
                    "die_offset",
                    "attribute_name",
                    "target_offset",
                    "relation",
                ),
                order_by=("unit_offset", "die_offset", "attribute_name"),
                operation="prefetch_reference_targets",
            )
            for row in rows:
                _record_reference_row(row, wanted, target_cache, targets)
    loaded.update(keys)
    return tuple(sorted(targets))


def _reference_caches(
    store: _DorisHydrationStore,
) -> tuple[dict[tuple[int | None, int, str], int | None], set[tuple[int, int]]]:
    return store._reference_targets, store._reference_loaded


def _record_reference_row(
    row: Mapping[str, Any],
    wanted: set[tuple[int, int]],
    target_cache: dict[tuple[int | None, int, str], int | None],
    targets: set[int],
) -> None:
    unit_offset = _as_int(row.get("unit_offset"))
    die_offset = _as_int(row.get("die_offset"))
    name = row.get("attribute_name")
    if unit_offset is None or die_offset is None or not isinstance(name, str):
        return
    key = (unit_offset, die_offset)
    if key not in wanted:
        return
    target = _as_int(row.get("target_offset"))
    target_cache[(unit_offset, die_offset, name)] = target
    if target is not None:
        targets.add(target)


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


def _has_reference_attribute(die: DorisDie) -> bool:
    return any(
        name in _REFERENCE_NAMES or str(getattr(attribute, "form", "")).startswith("DW_FORM_ref")
        for name, attribute in die.attributes.items()
    )


def _unique_dies(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> tuple[DorisDie, ...]:
    result: list[DorisDie] = []
    seen: set[tuple[int, int]] = set()
    for die in dies:
        unit_offset = store._die_unit_offsets.get(die.offset)
        if unit_offset is None:
            unit_offset = die.cu.cu_offset
        key = (unit_offset, die.offset)
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

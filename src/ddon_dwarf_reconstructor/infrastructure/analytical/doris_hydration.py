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


class _DorisHydrationStore(Protocol):
    """Private store surface used by the bounded hydration functions."""

    _dies: dict[int, DorisDie]
    _die_unit_offsets: dict[int, int]
    _units: dict[int, DorisCompilationUnit]
    _child_tag_counts: dict[int, NestedTypeCounts]
    _reference_targets: dict[tuple[int | None, int, str], int | None]
    _reference_loaded: set[tuple[int, int]]

    def _rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
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
    rows: list[dict[str, Any]] = []
    for batch in batched(offsets):
        rows.extend(
            store._rows(
                "attribute",
                {"unit_offset": unit_offset, "die_offset": batch},
                order_by=("die_offset", "ordinal"),
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
    offsets = tuple(
        sorted({die.offset for die in dies if die.offset not in store._child_tag_counts})
    )
    for batch in batched(offsets):
        counts = {
            offset: {
                "DW_TAG_enumeration_type": 0,
                "DW_TAG_structure_type": 0,
                "DW_TAG_union_type": 0,
            }
            for offset in batch
        }
        for row in store._rows(
            "die",
            {"parent_offset": batch},
            columns=("parent_offset", "tag", "is_null"),
        ):
            parent_offset = _as_int(row.get("parent_offset"))
            tag = row.get("tag")
            if parent_offset in counts and not row.get("is_null") and tag in counts[parent_offset]:
                counts[parent_offset][tag] += 1
        for offset, values in counts.items():
            store._child_tag_counts[offset] = NestedTypeCounts(
                enums=values["DW_TAG_enumeration_type"],
                structs=values["DW_TAG_structure_type"],
                unions=values["DW_TAG_union_type"],
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


def _hydrate_offsets(
    store: _DorisHydrationStore,
    offsets: Sequence[int],
) -> tuple[DorisDie, ...]:
    unique_offsets = tuple(dict.fromkeys(offsets))
    hydrated: list[DorisDie] = []
    metadata_columns = (
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
    for batch in batched(unique_offsets):
        die_rows = store._rows(
            "die",
            {"die_offset": batch},
            columns=metadata_columns,
            order_by=("unit_offset", "ordinal"),
        )
        if not die_rows:
            continue
        unit_offsets = tuple(
            sorted(
                {int(row["unit_offset"]) for row in die_rows if row.get("unit_offset") is not None}
            )
        )
        _hydrate_units(store, unit_offsets)
        attribute_rows = store._rows(
            "attribute",
            {"die_offset": batch},
            order_by=("unit_offset", "die_offset", "ordinal"),
        )
        attributes = _group_attributes_by_key(attribute_rows)
        for row in die_rows:
            unit_offset = _as_int(row.get("unit_offset"))
            die_offset = _as_int(row.get("die_offset"))
            if unit_offset is None or die_offset is None:
                continue
            if store._die_unit_offsets.get(die_offset) == unit_offset and die_offset in store._dies:
                hydrated.append(store._dies[die_offset])
                continue
            hydrated.append(
                store._die_from_record(row, attributes.get((unit_offset, die_offset), ()))
            )
    return _unique_dies(store, hydrated)


def _hydrate_units(store: _DorisHydrationStore, offsets: Sequence[int]) -> None:
    missing = tuple(offset for offset in offsets if offset not in store._units)
    for batch in batched(missing):
        for row in store._rows(
            "unit",
            {"unit_offset": batch},
            order_by=("unit_offset",),
        ):
            store._unit_from_record(row)


def _reference_keys(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> tuple[tuple[int, int], ...]:
    loaded = getattr(store, "_reference_loaded", set())
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
    offsets = tuple(dict.fromkeys(die for _unit, die in keys))
    wanted = set(keys)
    for batch in batched(offsets):
        rows = store._rows(
            "reference",
            {"die_offset": batch, "relation": "attribute_reference"},
            columns=(
                "unit_offset",
                "die_offset",
                "attribute_name",
                "target_offset",
                "relation",
            ),
            order_by=("unit_offset", "die_offset", "attribute_name"),
        )
        for row in rows:
            _record_reference_row(row, wanted, target_cache, targets)
    loaded.update(keys)
    return tuple(sorted(targets))


def _reference_caches(
    store: _DorisHydrationStore,
) -> tuple[dict[tuple[int | None, int, str], int | None], set[tuple[int, int]]]:
    target_cache = getattr(store, "_reference_targets", None)
    if target_cache is None:
        target_cache = {}
        store._reference_targets = target_cache
    loaded = getattr(store, "_reference_loaded", None)
    if loaded is None:
        loaded = set()
        store._reference_loaded = loaded
    return target_cache, loaded


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

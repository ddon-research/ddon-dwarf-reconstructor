"""Bounded reference-target hydration for the Doris serving adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ...domain.models.analytical_dwarf import QueryStatus
from .bounded_query_cache import BoundedQueryCache
from .doris_batch_rows import hydration_rows
from .doris_models import DorisDie
from .dwarf_reference import reference_target_for_attribute

if TYPE_CHECKING:
    from .doris_hydration import _DorisHydrationStore


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
_REFERENCE_BATCH_SIZE = 512
DieKey = tuple[int, int]


def prefetch_references(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
    *,
    max_keys: int = _REFERENCE_BATCH_SIZE,
) -> None:
    """Load a bounded reference frontier for already-hydrated DIEs."""
    if max_keys < 1:
        raise ValueError("maximum reference batch must be positive")
    keys = reference_keys(store, dies)
    if not keys:
        return
    for start in range(0, len(keys), max_keys):
        load_reference_targets(store, keys[start : start + max_keys])


def reference_candidates(
    store: _DorisHydrationStore,
    current: DorisDie,
) -> Iterable[DorisDie]:
    """Yield the current DIE followed by the newest cached candidates."""
    yield current
    indexed_by_key = getattr(store, "_reference_dies_by_key", None)
    dies_by_key = getattr(store, "_dies_by_key", None)
    if indexed_by_key is not None and dies_by_key is not None:
        candidates = tuple(
            die
            for key in reversed(tuple(indexed_by_key))
            if (die := dies_by_key.get(key)) is not None
        )
    else:
        indexed = getattr(store, "_reference_dies", None)
        if indexed is None:
            candidates = tuple(store._dies.values())
        else:
            candidates = tuple(
                die
                for offset in reversed(tuple(indexed))
                if (die := store._dies.get(offset)) is not None
            )
    for die in candidates:
        if (die.cu.cu_offset, die.offset) != (current.cu.cu_offset, current.offset):
            yield die


def register_reference_candidate(store: _DorisHydrationStore, die: DorisDie) -> None:
    """Index hydrated DIEs that can contribute reference targets."""
    indexed = getattr(store, "_reference_dies", None)
    indexed_by_key = getattr(store, "_reference_dies_by_key", None)
    if indexed_by_key is not None and has_reference_attribute(die):
        indexed_by_key[(die.cu.cu_offset, die.offset)] = None
    elif indexed is not None and has_reference_attribute(die):
        indexed[die.offset] = None


def reference_keys(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> tuple[tuple[int, int], ...]:
    """Return unloaded DIE keys whose attributes may contain references."""
    loaded = store._reference_loaded
    result: list[tuple[int, int]] = []
    for die in dies:
        unit_offset = die.cu.cu_offset
        key = (unit_offset, die.offset)
        if key in loaded or not has_reference_attribute(die):
            continue
        if _cache_inline_reference_targets(store, die, unit_offset):
            loaded.add(key)
            continue
        result.append(key)
    return tuple(dict.fromkeys(result))


def cached_reference_target_offsets(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> set[int]:
    """Return target offsets decoded inline or by a previous reference query."""
    targets: set[int] = set()
    for die in dies:
        unit_offset = die.cu.cu_offset
        for name, attribute in die.attributes.items():
            if not is_reference_attribute(name, str(getattr(attribute, "form", ""))):
                continue
            target = store._reference_targets.get((unit_offset, die.offset, name))
            if target is not None:
                targets.add(target)
    return targets


def cached_reference_target_keys(
    store: _DorisHydrationStore,
    dies: Iterable[DorisDie],
) -> set[DieKey]:
    """Return cached targets with the CU needed for collision-safe hydration."""
    targets: set[DieKey] = set()
    for die in dies:
        unit_offset = die.cu.cu_offset
        for name, attribute in die.attributes.items():
            if not is_reference_attribute(name, str(getattr(attribute, "form", ""))):
                continue
            target = store._reference_targets.get((unit_offset, die.offset, name))
            if target is not None:
                targets.add((unit_offset, target))
    return targets


def load_reference_targets(
    store: _DorisHydrationStore,
    keys: Sequence[tuple[int, int]],
) -> tuple[DieKey, ...]:
    """Load target offsets for a bounded set of source-bound DIE keys."""
    targets: set[DieKey] = set()
    target_cache, loaded = _reference_caches(store)
    wanted = set(keys)
    for unit_offset, offsets in _group_keys_by_unit(store, keys):
        for batch in _batches(offsets):
            filters: dict[str, object] = {
                "die_offset": batch,
                "relation": "attribute_reference",
            }
            if store._hydration_scope == "unit" and unit_offset is not None:
                filters["unit_offset"] = unit_offset
            rows = hydration_rows(
                store,
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


def has_reference_attribute(die: DorisDie) -> bool:
    return any(
        is_reference_attribute(name, str(getattr(attribute, "form", "")))
        for name, attribute in die.attributes.items()
    )


def is_reference_attribute(name: str, form: str) -> bool:
    return form.startswith("DW_FORM_ref") or name in _REFERENCE_NAMES


def _cache_inline_reference_targets(
    store: _DorisHydrationStore,
    die: DorisDie,
    unit_offset: int,
) -> bool:
    """Cache complete references already decoded on a hydrated DIE."""
    complete = True
    found = False
    for name, attribute in die.attributes.items():
        if not is_reference_attribute(name, attribute.form):
            continue
        found = True
        target, status = reference_target_for_attribute(attribute, unit_offset=unit_offset)
        if status is not QueryStatus.COMPLETE:
            complete = False
            continue
        store._reference_targets[(unit_offset, die.offset, name)] = target
    return found and complete


def _reference_caches(
    store: _DorisHydrationStore,
) -> tuple[
    BoundedQueryCache[tuple[int | None, int, str], int | None],
    set[tuple[int, int]],
]:
    return store._reference_targets, store._reference_loaded


def _record_reference_row(
    row: Mapping[str, Any],
    wanted: set[tuple[int, int]],
    target_cache: BoundedQueryCache[tuple[int | None, int, str], int | None],
    targets: set[DieKey],
) -> None:
    unit_offset = _as_int(row.get("unit_offset"))
    die_offset = _as_int(row.get("die_offset"))
    name = row.get("attribute_name")
    if unit_offset is None or die_offset is None or not isinstance(name, str):
        return
    if (unit_offset, die_offset) not in wanted:
        return
    target = _as_int(row.get("target_offset"))
    target_cache[(unit_offset, die_offset, name)] = target
    if target is not None:
        targets.add((unit_offset, target))


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


def _batches(values: Sequence[int]) -> Iterable[tuple[int, ...]]:
    for start in range(0, len(values), _REFERENCE_BATCH_SIZE):
        yield tuple(values[start : start + _REFERENCE_BATCH_SIZE])


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

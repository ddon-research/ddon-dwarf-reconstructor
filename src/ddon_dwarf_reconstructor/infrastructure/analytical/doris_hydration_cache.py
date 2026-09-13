"""CU-qualified cache helpers shared by Doris hydration paths."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ...domain.services.definition_selection import NestedTypeCounts
from .doris_models import DorisDie

if TYPE_CHECKING:
    from .doris_hydration import _DorisHydrationStore

DieKey = tuple[int, int]


def die_key(die: DorisDie) -> DieKey:
    return die.cu.cu_offset, die.offset


def cached_die(store: _DorisHydrationStore, key: DieKey) -> DorisDie | None:
    exact = getattr(store, "_dies_by_key", None)
    if exact is not None:
        cached = exact.get(key)
        if cached is not None:
            return cached
    unit_offset, die_offset = key
    cached = store._dies.get(die_offset)
    return (
        cached
        if cached is not None and store._die_unit_offsets.get(die_offset) == unit_offset
        else None
    )


def cache_contains_key(cache: Mapping[Any, Any], key: DieKey, offset: int) -> bool:
    return key in cache or offset in cache


def children_cached(store: _DorisHydrationStore, key: DieKey) -> bool:
    exact = getattr(store, "_children_by_key", None)
    if exact is not None:
        return key in exact
    return key[1] in store._children


def children_cache_set(
    store: _DorisHydrationStore,
    key: DieKey,
    children: tuple[DorisDie, ...],
) -> None:
    exact = getattr(store, "_children_by_key", None)
    if exact is not None:
        exact[key] = children
    if key[1] not in store._children:
        store._children[key[1]] = children


def child_tag_count_cache_set(
    store: _DorisHydrationStore,
    key: tuple[int | None, int],
    value: NestedTypeCounts,
) -> None:
    exact = getattr(store, "_child_tag_counts_by_key", None)
    if exact is not None and key[0] is not None:
        exact[key] = value
    if key[1] not in store._child_tag_counts:
        store._child_tag_counts[key[1]] = value


__all__ = [
    "DieKey",
    "cache_contains_key",
    "cached_die",
    "child_tag_count_cache_set",
    "children_cache_set",
    "children_cached",
    "die_key",
]

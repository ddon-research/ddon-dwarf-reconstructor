"""Bounded request-cache behavior tests."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.bounded_query_cache import (
    BoundedQueryCache,
)

pytestmark = [pytest.mark.unit, pytest.mark.non_functional]


def test_query_cache_evicts_oldest_entry_and_refreshes_lookup() -> None:
    cache: BoundedQueryCache[str, int] = BoundedQueryCache(max_size=2)
    cache["first"] = 1
    cache["second"] = 2

    assert cache.lookup("first") == 1
    cache["third"] = 3

    assert "second" not in cache
    assert cache.lookup("first") == 1
    assert cache.lookup("third") == 3
    assert cache.evictions == 1


def test_query_cache_rejects_zero_capacity() -> None:
    with pytest.raises(ValueError, match="positive"):
        BoundedQueryCache(max_size=0)

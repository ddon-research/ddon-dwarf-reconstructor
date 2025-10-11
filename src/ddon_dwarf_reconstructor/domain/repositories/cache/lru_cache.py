#!/usr/bin/env python3

"""LRU cache implementation for DWARF data caching."""

from collections import OrderedDict
from typing import Any


class LRUCache:
    """Simple LRU cache implementation with configurable size limits."""

    def __init__(self, max_size: int = 10000):
        """Initialize LRU cache with maximum size.

        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict[int, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: int) -> Any | None:
        """Get item from cache, moving it to end (most recently used).

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if key in self.cache:
            # Move to end (most recently used)
            value = self.cache.pop(key)
            self.cache[key] = value
            self.hits += 1
            return value

        self.misses += 1
        return None

    def put(self, key: int, value: Any) -> None:
        """Add item to cache, evicting oldest if necessary.

        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self.cache:
            # Update existing key - move to end
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            # Remove oldest item (first in OrderedDict)
            self.cache.popitem(last=False)

        self.cache[key] = value

    def clear(self) -> None:
        """Clear all cached items."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
        }

    def __len__(self) -> int:
        """Return current cache size."""
        return len(self.cache)

    def __contains__(self, key: int) -> bool:
        """Check if key exists in cache without affecting LRU order."""
        return key in self.cache

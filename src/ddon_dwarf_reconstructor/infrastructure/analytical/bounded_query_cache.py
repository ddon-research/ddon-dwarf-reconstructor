"""Small bounded LRU cache for source-bound definition query results."""

from __future__ import annotations

from collections import OrderedDict
from typing import TypeVar

Key = TypeVar("Key")
Value = TypeVar("Value")


class BoundedQueryCache(OrderedDict[Key, Value]):
    """Dictionary-compatible LRU cache with an explicit memory bound."""

    def __init__(self, max_size: int = 512) -> None:
        if max_size < 1:
            raise ValueError("query cache size must be positive")
        super().__init__()
        self.max_size = max_size
        self.evictions = 0

    def lookup(self, key: Key, default: Value | None = None) -> Value | None:
        try:
            value = self[key]
        except KeyError:
            return default
        self.move_to_end(key)
        return value

    def __setitem__(self, key: Key, value: Value) -> None:
        if key in self:
            super().__delitem__(key)
        elif len(self) >= self.max_size:
            self.popitem(last=False)
            self.evictions += 1
        super().__setitem__(key, value)

    def clear(self) -> None:
        super().clear()
        self.evictions = 0


__all__ = ["BoundedQueryCache"]

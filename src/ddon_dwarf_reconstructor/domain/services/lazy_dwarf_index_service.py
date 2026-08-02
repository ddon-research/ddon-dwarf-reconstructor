#!/usr/bin/env python3

"""Compatibility façade for bounded, offset-based DWARF lookups."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from ...core.dwarf import DwarfInfo
from ...core.observability import get_logger
from ..ports.cache import SymbolCachePort
from ..repositories.cache import LRUCache, PersistentSymbolCache
from .lazy_index_context import LazyIndexContext
from .lazy_index_discovery import LazyIndexDiscoveryMixin
from .lazy_index_lookup import LazyIndexLookupMixin
from .lazy_index_search import LazyIndexSearchMixin
from .lazy_index_source import LazyIndexSourceMixin

logger = get_logger(__name__)


class LazyDwarfIndexService(
    LazyIndexSourceMixin,
    LazyIndexLookupMixin,
    LazyIndexDiscoveryMixin,
    LazyIndexSearchMixin,
):
    """Preserve the public index API while delegating focused responsibilities."""

    persistent_cache: SymbolCachePort

    def __init__(
        self,
        dwarf_info: DwarfInfo,
        cache_file: str = ".dwarf_cache.json",
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
        source_file_path: str | Path | None = None,
    ) -> None:
        self.dwarf_info = dwarf_info
        source_fingerprint = (
            self._source_fingerprint(Path(source_file_path))
            if source_file_path is not None
            else None
        )
        validator: Callable[[dict[str, Any]], bool] | None = None
        if source_fingerprint is not None:
            context = cast(LazyIndexContext, self)

            def validate_cache(data: dict[str, Any]) -> bool:
                return LazyIndexSourceMixin._validate_unbound_cache(context, data)

            validator = validate_cache
        self.persistent_cache = PersistentSymbolCache(
            cache_file,
            source_fingerprint,
            validator,
        )
        self.die_cache = LRUCache(die_cache_size)
        self.type_cache = LRUCache(type_cache_size)
        self._discovered_symbols: set[str] = set()
        logger.info(
            "Initialized LazyDwarfIndexService with die_cache=%s, type_cache=%s",
            die_cache_size,
            type_cache_size,
        )

    def save_cache(self) -> None:
        """Publish persistent symbol mappings atomically."""
        self.persistent_cache.save()

    def get_stats(self) -> dict[str, Any]:
        """Return runtime and persistent cache statistics."""
        return {
            "die_cache": self.die_cache.stats(),
            "type_cache": self.type_cache.stats(),
            "persistent_cache": self.persistent_cache.get_statistics(),
            "discovered_symbols": len(self._discovered_symbols),
        }

    def clear_runtime_caches(self) -> None:
        """Clear bounded in-memory caches without touching durable indexes."""
        self.die_cache.clear()
        self.type_cache.clear()
        logger.info("Runtime caches cleared")

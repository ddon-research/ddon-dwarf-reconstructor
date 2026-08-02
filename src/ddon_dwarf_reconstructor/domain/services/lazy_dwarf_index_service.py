#!/usr/bin/env python3

"""Bounded, offset-based DWARF lookup service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ...core.dwarf import DwarfInfo
from ...core.observability import get_logger, log_event
from ..ports.cache import SymbolCachePort
from ..ports.source_identity import SourceIdentityPort
from ..repositories.cache import LRUCache, PersistentSymbolCache
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
    """Coordinate source-bound index lookup, discovery, and search operations."""

    persistent_cache: SymbolCachePort

    def __init__(
        self,
        dwarf_info: DwarfInfo,
        cache_file: str = ".dwarf_cache.json",
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
        search_timeout: float = 1.0,
        source_file_path: str | Path | None = None,
        source_identity: SourceIdentityPort | None = None,
    ) -> None:
        self.dwarf_info = dwarf_info
        if search_timeout <= 0:
            raise ValueError("search_timeout must be positive")
        self.search_timeout = search_timeout
        source_fingerprint = (
            self._source_fingerprint(source_identity, Path(source_file_path))
            if source_file_path is not None and source_identity is not None
            else None
        )
        self.persistent_cache = PersistentSymbolCache(
            cache_file,
            source_fingerprint,
        )
        self.die_cache = LRUCache(die_cache_size)
        self.type_cache = LRUCache(type_cache_size)
        self._discovered_symbols: set[str] = set()
        log_event(
            logger,
            logging.DEBUG,
            "dwarf_index_service_initialized",
            cache_file=cache_file,
            die_cache_size=die_cache_size,
            type_cache_size=type_cache_size,
            search_timeout_seconds=search_timeout,
            source_bound=source_fingerprint is not None,
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
        log_event(logger, logging.DEBUG, "dwarf_runtime_caches_cleared")

#!/usr/bin/env python3

"""Compatibility façade for persistent symbol and definition caching."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ....infrastructure.logging import get_logger
from .cache_context import CacheContext
from .cache_definitions import CacheDefinitionsMixin
from .cache_persistence import CachePersistenceMixin
from .cache_schema import CacheSchemaMixin
from .cache_validation import CacheValidationMixin

logger = get_logger(__name__)


class PersistentSymbolCache(
    CacheSchemaMixin,
    CachePersistenceMixin,
    CacheDefinitionsMixin,
    CacheValidationMixin,
):
    """Compatibility façade for schema, persistence, definition, and repair services."""

    CURRENT_VERSION = "4.0"
    LOCK_TIMEOUT_SECONDS = 10.0
    STALE_LOCK_SECONDS = 60.0

    def __init__(
        self,
        cache_file: str | Path,
        source_fingerprint: dict[str, int | str] | None = None,
        unbound_cache_validator: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        """Initialize persistent cache.

        Args:
            cache_file: Path to cache file
        """
        self.cache_file = Path(cache_file)
        self.source_fingerprint = source_fingerprint
        self.unbound_cache_validator = unbound_cache_validator
        self._modified = False  # Initialize before loading
        self.data = self._load_cache()  # May set _modified during cleanup

    def _new_cache(self, cache_file: str | Path) -> CacheContext:
        """Construct a cache of the same concrete type for repair operations."""
        return type(self)(cache_file)

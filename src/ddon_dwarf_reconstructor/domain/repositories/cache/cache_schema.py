"""Focused persistent-symbol-cache operations."""

from __future__ import annotations

import json
from time import time
from typing import Any

from ....core.observability import get_logger
from .cache_context import CacheContext

logger = get_logger(__name__)


class CacheSchemaMixin:
    def _load_cache(self: CacheContext) -> dict[str, Any]:
        """Load cached mappings from disk.

        Returns:
            Cache data dictionary

        Raises:
            ValueError: If cache contains corrupted data (duplicate keys detected)
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if not isinstance(loaded, dict):
                        raise ValueError("cache root must be a JSON object")
                    data: dict[str, Any] = loaded
                    if data.get("version") != self.CURRENT_VERSION:
                        logger.info(
                            "Ignoring cache with schema %s; expected %s: %s",
                            data.get("version", "missing"),
                            self.CURRENT_VERSION,
                            self.cache_file,
                        )
                        return self._create_empty_cache()
                    if not self._has_current_shape(data):
                        logger.warning(
                            "Ignoring structurally incomplete cache; rebuilding from source: %s",
                            self.cache_file,
                        )
                        return self._create_empty_cache()
                    if (
                        self.source_fingerprint is not None
                        and data.get("source_fingerprint") != self.source_fingerprint
                    ):
                        logger.info("Ignoring cache from a different source: %s", self.cache_file)
                        return self._create_empty_cache()
                    # Validate cache integrity, attempting auto-repair before failing hard.
                    try:
                        self._validate_cache_integrity(data)
                    except ValueError:
                        logger.warning(
                            f"Cache integrity issue detected in {self.cache_file}; attempting auto-repair"
                        )
                        self.data = data
                        report = self.validate_and_repair()
                        self._validate_cache_integrity(self.data)
                        logger.info(
                            f"Auto-repaired cache from {self.cache_file} "
                            f"({len(report['repairs'])} repairs, {len(report['issues'])} issues)"
                        )
                        return self.data
                    logger.info(
                        f"Loaded cache from {self.cache_file} "
                        f"({len(data.get('symbol_to_offset', {}))} symbols)"
                    )
                    return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}", exc_info=e)

        # Return empty cache structure
        return self._create_empty_cache()

    @staticmethod
    def _has_current_shape(data: dict[str, Any]) -> bool:
        """Return whether a document has the complete current cache shape."""
        required_maps = (
            "symbol_to_offset",
            "offset_to_symbol",
            "symbol_to_cu_offset",
            "symbol_definitions",
            "cu_offset_to_symbols",
        )
        return "source_fingerprint" in data and all(
            isinstance(data.get(field), dict) for field in required_maps
        )

    def _validate_cache_integrity(self: CacheContext, data: dict[str, Any]) -> None:
        """Validate cache data integrity.

        Checks that cu_offset_to_symbols is consistent with symbol_to_cu_offset.
        If inconsistencies are detected (e.g., from duplicate keys), raises an error.

        Args:
            data: Cache data to validate

        Raises:
            ValueError: If cache is corrupted (duplicate keys or inconsistent data)
        """
        if not self._has_current_shape(data):
            raise ValueError("cache document does not have the current structure")

        # Rebuild expected mapping from symbol_to_cu_offset
        expected: dict[str, set[str]] = {}
        for symbol, cu_offset in data["symbol_to_cu_offset"].items():
            cu_key = str(cu_offset)
            if cu_key not in expected:
                expected[cu_key] = set()
            expected[cu_key].add(symbol)

        # Check actual mapping
        actual: dict[str, set[str]] = {
            cu_key: set(symbols) for cu_key, symbols in data["cu_offset_to_symbols"].items()
        }

        # Find discrepancies
        if expected != actual:
            missing_symbols = []
            for cu_key, exp_symbols in expected.items():
                act_symbols = actual.get(cu_key, set())
                if exp_symbols != act_symbols:
                    missing = exp_symbols - act_symbols
                    if missing:
                        missing_symbols.append(f"CU {cu_key}: missing {missing}")

            error_msg = (
                f"Cache file has inconsistent mappings (likely from interrupted write or corruption).\n"
                f"\n"
                f"RECOMMENDED RECOVERY STEPS:\n"
                f"1. Try automatic repair: Run with --validate-cache flag\n"
                f"2. If repair fails: Check disk space and file permissions\n"
                f"3. Last resort: Delete cache file and regenerate:\n"
                f"   rm {self.cache_file}\n"
                f"   # Then re-run your command\n"
                f"\n"
                f"Note: Cache regeneration can take 10-60 minutes for exhaustive mode.\n"
                f"\n"
                f"Inconsistencies found:\n  " + "\n  ".join(missing_symbols)
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _create_empty_cache(self: CacheContext) -> dict[str, Any]:
        """Create empty cache structure with multi-definition support.

        Returns:
            Empty cache dictionary
        """
        return {
            "version": self.CURRENT_VERSION,
            "source_fingerprint": self.source_fingerprint,
            "symbol_to_offset": {},  # Primary definition only
            "offset_to_symbol": {},
            "symbol_to_cu_offset": {},  # Primary CU only
            "symbol_definitions": {},  # NEW: multi-definition tracking
            "cu_offset_to_symbols": {},
            "created": time(),
            "last_updated": time(),
        }

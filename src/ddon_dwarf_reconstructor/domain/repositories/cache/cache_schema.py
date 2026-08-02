"""Focused persistent-symbol-cache operations."""

from __future__ import annotations

import json
from time import time
from typing import Any

from ....infrastructure.logging import get_logger
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
                    data: dict[str, Any] = json.load(f)
                    if (
                        self.source_fingerprint is not None
                        and data.get("source_fingerprint") != self.source_fingerprint
                    ):
                        is_valid_unbound_cache = (
                            data.get("source_fingerprint") is None
                            and self.unbound_cache_validator is not None
                            and self.unbound_cache_validator(data)
                        )
                        if not is_valid_unbound_cache:
                            logger.info(
                                f"Ignoring cache from different source fingerprint: {self.cache_file}"
                            )
                            return self._create_empty_cache()
                    # Migrate cache format if needed
                    data = self._migrate_cache_format(data)
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
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}")

        # Return empty cache structure
        return self._create_empty_cache()

    def _validate_cache_integrity(self: CacheContext, data: dict[str, Any]) -> None:
        """Validate cache data integrity.

        Checks that cu_offset_to_symbols is consistent with symbol_to_cu_offset.
        If inconsistencies are detected (e.g., from duplicate keys), raises an error.

        Args:
            data: Cache data to validate

        Raises:
            ValueError: If cache is corrupted (duplicate keys or inconsistent data)
        """
        if "symbol_to_cu_offset" not in data or "cu_offset_to_symbols" not in data:
            return  # Empty or incomplete cache, nothing to validate

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

    def _migrate_cache_format(self: CacheContext, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate cache data to current format with multi-definition support.

        Args:
            data: Loaded cache data

        Returns:
            Migrated cache data
        """
        version = data.get("version", "1.0")

        if version == "1.0":
            logger.info("Migrating cache from v1.0 to v1.1 (adding CU mapping support)")
            data["version"] = "1.1"
            data["symbol_to_cu_offset"] = {}
            data["cu_offset_to_symbols"] = {}
            self._modified = True

        if version in ("1.0", "1.1", "2.0"):
            logger.info(f"Migrating cache from v{version} to v3.0 (multi-definition support)")
            data["version"] = "3.0"
            # Initialize multi-definition tracking from existing single-definition data
            data["symbol_definitions"] = {}
            for symbol, cu_offset in data.get("symbol_to_cu_offset", {}).items():
                die_offset = data.get("symbol_to_offset", {}).get(symbol)
                if die_offset is not None:
                    # Convert single definition to multi-definition format
                    data["symbol_definitions"][symbol] = [
                        {
                            "cu_offset": cu_offset,
                            "die_offset": die_offset,
                            "score": 0,  # Unknown score for migrated entries
                            "complete": True,  # Assume complete for backward compat
                        }
                    ]
            self._modified = True

        if version in ("1.0", "1.1", "2.0", "3.0"):
            logger.info(f"Migrating cache from v{version} to v{self.CURRENT_VERSION}")
            data["version"] = self.CURRENT_VERSION
            data["source_fingerprint"] = self.source_fingerprint
            self._modified = True

        # Ensure all required fields exist
        empty_cache = self._create_empty_cache()
        for key, default_value in empty_cache.items():
            if key not in data:
                data[key] = default_value
                self._modified = True

        return data

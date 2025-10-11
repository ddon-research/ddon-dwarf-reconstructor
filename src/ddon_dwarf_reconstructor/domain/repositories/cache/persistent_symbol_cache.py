#!/usr/bin/env python3

"""Persistent symbol cache for DWARF parsing."""

import json
from pathlib import Path
from time import time
from typing import Any

from ....infrastructure.logging import get_logger

logger = get_logger(__name__)


class PersistentSymbolCache:
    """Manages disk-based symbol→offset mappings."""

    def __init__(self, cache_file: str | Path):
        """Initialize persistent cache.

        Args:
            cache_file: Path to cache file
        """
        self.cache_file = Path(cache_file)
        self._modified = False  # Initialize before loading
        self.data = self._load_cache()  # May set _modified during cleanup

    def _load_cache(self) -> dict[str, Any]:
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
                    # Validate cache integrity
                    self._validate_cache_integrity(data)
                    logger.info(
                        f"Loaded cache from {self.cache_file} "
                        f"({len(data.get('symbol_to_offset', {}))} symbols)"
                    )
                    return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}")

        # Return empty cache structure
        return self._create_empty_cache()

    def _validate_cache_integrity(self, data: dict[str, Any]) -> None:
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
                f"Cache file is corrupted (likely from duplicate keys).\n"
                f"Delete the cache file and regenerate: {self.cache_file}\n"
                f"Inconsistencies found:\n  " + "\n  ".join(missing_symbols)
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _create_empty_cache(self) -> dict[str, Any]:
        """Create empty cache structure with simplified format.

        Returns:
            Empty cache dictionary
        """
        return {
            "version": "2.0",  # Simplified version without legacy sections
            "symbol_to_offset": {},
            "offset_to_symbol": {},
            "symbol_to_cu_offset": {},
            "cu_offset_to_symbols": {},
            "created": time(),
            "last_updated": time(),
        }

    def _migrate_cache_format(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate cache data to current format.

        Args:
            data: Loaded cache data

        Returns:
            Migrated cache data
        """
        version = data.get("version", "1.0")

        if version == "1.0":
            logger.info("Migrating cache from v1.0 to v1.1 (adding CU mapping support)")
            # Add new CU mapping fields
            data["version"] = "1.1"
            data["symbol_to_cu_offset"] = {}
            data["cu_offset_to_symbols"] = {}
            # Mark as modified to save upgraded format
            self._modified = True

        # Ensure all required fields exist
        empty_cache = self._create_empty_cache()
        for key, default_value in empty_cache.items():
            if key not in data:
                data[key] = default_value
                self._modified = True

        return data

    def get_symbol_offset(self, symbol_name: str) -> int | None:
        """Get offset for symbol.

        Args:
            symbol_name: Name of symbol

        Returns:
            Symbol offset or None if not found
        """
        result = self.data["symbol_to_offset"].get(symbol_name)
        return int(result) if result is not None else None

    def add_symbol(self, symbol_name: str, offset: int) -> None:
        """Add symbol→offset mapping.

        Args:
            symbol_name: Name of symbol
            offset: DWARF offset
        """
        if symbol_name not in self.data["symbol_to_offset"]:
            self.data["symbol_to_offset"][symbol_name] = offset
            self.data["offset_to_symbol"][str(offset)] = symbol_name
            self.data["last_updated"] = time()
            self._modified = True

    def get_symbol_by_offset(self, offset: int) -> str | None:
        """Get symbol name by offset.

        Args:
            offset: DWARF offset

        Returns:
            Symbol name or None if not found
        """
        result = self.data["offset_to_symbol"].get(str(offset))
        return str(result) if result is not None else None

    def save(self) -> None:
        """Save cache to disk if modified."""
        if self._modified:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                logger.info(
                    f"Saved cache to {self.cache_file} "
                    f"({len(self.data['symbol_to_offset'])} symbols)"
                )
                self._modified = False
            except OSError as e:
                logger.error(f"Failed to save cache to {self.cache_file}: {e}")

    def get_symbol_cu_offset(self, symbol_name: str) -> int | None:
        """Get CU offset for symbol for efficient CU targeting.

        Args:
            symbol_name: Name of symbol to look up

        Returns:
            CU offset if found, None otherwise
        """
        result = self.data["symbol_to_cu_offset"].get(symbol_name)
        return int(result) if result is not None else None

    def add_symbol_cu_mapping(self, symbol_name: str, cu_offset: int, die_offset: int) -> None:
        """Add symbol to CU offset mapping for efficient targeting.

        Args:
            symbol_name: Symbol name (e.g., "MtObject", "u32")
            cu_offset: Offset of compilation unit containing the symbol
            die_offset: Offset of DIE within the CU
        """
        # Convert cu_offset to string for consistent JSON key handling
        cu_key = str(cu_offset)

        # Store both CU and DIE mappings using the symbol name
        self.data["symbol_to_offset"][symbol_name] = die_offset
        self.data["offset_to_symbol"][str(die_offset)] = symbol_name
        self.data["symbol_to_cu_offset"][symbol_name] = cu_offset

        # Track symbols per CU using string key
        cu_symbols = self.data["cu_offset_to_symbols"].setdefault(cu_key, [])
        if symbol_name not in cu_symbols:
            cu_symbols.append(symbol_name)

        self.data["last_updated"] = time()
        self._modified = True

    def get_cu_symbols(self, cu_offset: int) -> list[str]:
        """Get all symbols known to be in a specific CU.

        Args:
            cu_offset: Offset of compilation unit

        Returns:
            List of symbol names in the CU
        """
        # Convert to string key for consistent lookup
        cu_key = str(cu_offset)
        result = self.data["cu_offset_to_symbols"].get(cu_key, [])
        return list(result) if isinstance(result, list) else []

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "symbols": len(self.data["symbol_to_offset"]),
            "cu_mappings": len(self.data["symbol_to_cu_offset"]),
            "compilation_units": len(self.data["cu_offset_to_symbols"]),
            "file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
            "last_updated": self.data.get("last_updated", 0),
        }

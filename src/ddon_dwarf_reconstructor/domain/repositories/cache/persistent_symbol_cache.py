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
                    # Migrate cache format if needed
                    data = self._migrate_cache_format(data)
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

    def _create_empty_cache(self) -> dict[str, Any]:
        """Create empty cache structure with multi-definition support.

        Returns:
            Empty cache dictionary
        """
        return {
            "version": "3.0",  # Multi-definition support
            "symbol_to_offset": {},  # Primary definition only
            "offset_to_symbol": {},
            "symbol_to_cu_offset": {},  # Primary CU only
            "symbol_definitions": {},  # NEW: multi-definition tracking
            "cu_offset_to_symbols": {},
            "created": time(),
            "last_updated": time(),
        }

    def _migrate_cache_format(self, data: dict[str, Any]) -> dict[str, Any]:
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
                if die_offset:
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
        """Save cache to disk only if content actually changed.

        Compares current cache data against disk content, ignoring timestamps.
        Only writes to disk if symbol mappings have changed, reducing I/O.
        """
        if not self._modified:
            return

        # Load current disk content for comparison
        disk_data = self._load_disk_cache_for_comparison()

        # Compare content (ignore timestamps)
        if self._cache_content_unchanged(disk_data):
            logger.debug(
                f"Cache content unchanged (only timestamps differ), "
                f"skipping save to {self.cache_file}"
            )
            self._modified = False
            return

        # Content changed, proceed with save
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

    def _load_disk_cache_for_comparison(self) -> dict[str, Any]:
        """Load cache from disk for content comparison.

        Returns:
            Cache data from disk, or empty dict if file doesn't exist
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not load disk cache for comparison: {e}")

        return {}

    def _cache_content_unchanged(self, disk_data: dict[str, Any]) -> bool:
        """Compare cache data, ignoring timestamps.

        Args:
            disk_data: Data loaded from disk

        Returns:
            True if content is identical (except timestamps)
        """
        # If disk is empty, we have changes
        if not disk_data:
            return False

        # Compare all symbol mapping sections (ignore timestamps)
        return (
            self.data.get("symbol_to_offset") == disk_data.get("symbol_to_offset")
            and self.data.get("offset_to_symbol") == disk_data.get("offset_to_symbol")
            and self.data.get("symbol_to_cu_offset") == disk_data.get("symbol_to_cu_offset")
            and self.data.get("cu_offset_to_symbols") == disk_data.get("cu_offset_to_symbols")
        )

    def get_symbol_cu_offset(self, symbol_name: str) -> int | None:
        """Get CU offset for symbol for efficient CU targeting.

        Args:
            symbol_name: Name of symbol to look up

        Returns:
            CU offset if found, None otherwise
        """
        result = self.data["symbol_to_cu_offset"].get(symbol_name)
        return int(result) if result is not None else None

    def add_symbol_cu_mapping(
        self, symbol_name: str, cu_offset: int, die_offset: int, score: int = 0, complete: bool = True
    ) -> None:
        """Add symbol to CU offset mapping with multi-definition support.

        Supports multiple definitions of the same symbol across different CUs.
        Tracks score and completeness to help select best definition.

        Args:
            symbol_name: Symbol name (e.g., "MtObject", "u32")
            cu_offset: Offset of compilation unit containing the symbol
            die_offset: Offset of DIE within the CU
            score: Completeness score (higher = more complete)
            complete: Whether this is a complete definition (vs forward declaration)
        """
        # Convert cu_offset to string for consistent JSON key handling
        cu_key = str(cu_offset)

        # Initialize multi-definition list if needed
        if symbol_name not in self.data["symbol_definitions"]:
            self.data["symbol_definitions"][symbol_name] = []

        # Check if this exact definition already exists
        definitions = self.data["symbol_definitions"][symbol_name]
        existing = next(
            (d for d in definitions if d["cu_offset"] == cu_offset and d["die_offset"] == die_offset),
            None,
        )

        if existing:
            # Update score if new score is higher (better definition found)
            if score > existing["score"]:
                existing["score"] = score
                existing["complete"] = complete
                logger.debug(f"Updated {symbol_name} definition at CU 0x{cu_offset:x} with score {score}")
        else:
            # Add new definition
            definitions.append(
                {
                    "cu_offset": cu_offset,
                    "die_offset": die_offset,
                    "score": score,
                    "complete": complete,
                }
            )
            logger.debug(
                f"Added {symbol_name} definition at CU 0x{cu_offset:x} "
                f"(total: {len(definitions)} definitions)"
            )

        # Update primary definition (highest score complete definition, or highest score overall)
        best_def = self._get_best_definition(symbol_name)
        if best_def:
            self.data["symbol_to_offset"][symbol_name] = best_def["die_offset"]
            self.data["offset_to_symbol"][str(best_def["die_offset"])] = symbol_name
            self.data["symbol_to_cu_offset"][symbol_name] = best_def["cu_offset"]

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

    def _get_best_definition(self, symbol_name: str) -> dict[str, Any] | None:
        """Get best definition for symbol (highest score complete definition).

        Args:
            symbol_name: Symbol name to look up

        Returns:
            Best definition dict or None if no definitions exist
        """
        definitions = self.data["symbol_definitions"].get(symbol_name, [])
        if not definitions:
            return None

        # Prefer complete definitions with highest score
        complete_defs = [d for d in definitions if d.get("complete", True)]
        if complete_defs:
            return max(complete_defs, key=lambda d: d.get("score", 0))

        # Fallback to incomplete definition with highest score
        return max(definitions, key=lambda d: d.get("score", 0))

    def get_all_definitions(self, symbol_name: str) -> list[dict[str, Any]]:
        """Get all definitions for a symbol across different CUs.

        Args:
            symbol_name: Symbol name to look up

        Returns:
            List of definition dicts, sorted by score (descending)
        """
        definitions = self.data["symbol_definitions"].get(symbol_name, [])
        return sorted(definitions, key=lambda d: d.get("score", 0), reverse=True)

    def validate_and_repair(self) -> dict[str, Any]:
        """Validate cache integrity and attempt automatic repairs.

        Returns:
            Validation report with issues found and repairs made
        """
        report = {
            "valid": True,
            "issues": [],
            "repairs": [],
            "warnings": [],
        }

        # Check for missing required fields
        self._check_required_fields(report)

        # Check consistency between definitions and primary mappings
        self._check_primary_mappings(report)

        # Check for orphaned entries
        self._check_orphaned_entries(report)

        # Check for duplicate definitions
        self._check_duplicate_definitions(report)

        if self._modified:
            logger.info(f"Cache validation found {len(report['issues'])} issues, made {len(report['repairs'])} repairs")

        return report

    def _check_required_fields(self, report: dict[str, Any]) -> None:
        """Check for missing required fields and add them."""
        required_fields = ["symbol_to_offset", "symbol_to_cu_offset", "symbol_definitions", "cu_offset_to_symbols"]
        for field in required_fields:
            if field not in self.data:
                report["issues"].append(f"Missing required field: {field}")
                self.data[field] = {}
                report["repairs"].append(f"Added missing field: {field}")
                self._modified = True
                report["valid"] = False

    def _check_primary_mappings(self, report: dict[str, Any]) -> None:
        """Check consistency between symbol_definitions and primary mappings."""
        for symbol, definitions in self.data.get("symbol_definitions", {}).items():
            if not definitions:
                report["warnings"].append(f"Symbol {symbol} has empty definition list")
                continue

            best_def = self._get_best_definition(symbol)
            if not best_def:
                report["issues"].append(f"Symbol {symbol} has no valid best definition")
                continue

            # Verify primary mapping matches best definition
            primary_offset = self.data["symbol_to_offset"].get(symbol)
            if primary_offset != best_def["die_offset"]:
                report["issues"].append(
                    f"Symbol {symbol} primary offset mismatch: "
                    f"expected {best_def['die_offset']}, got {primary_offset}"
                )
                self.data["symbol_to_offset"][symbol] = best_def["die_offset"]
                report["repairs"].append(f"Fixed primary offset for {symbol}")
                self._modified = True

    def _check_orphaned_entries(self, report: dict[str, Any]) -> None:
        """Check for orphaned offset_to_symbol entries."""
        valid_offsets = {
            str(d["die_offset"]) for defs in self.data["symbol_definitions"].values() for d in defs
        }
        orphaned = set(self.data.get("offset_to_symbol", {}).keys()) - valid_offsets
        if orphaned:
            report["warnings"].append(f"Found {len(orphaned)} orphaned offset_to_symbol entries")
            for offset in orphaned:
                del self.data["offset_to_symbol"][offset]
            report["repairs"].append(f"Removed {len(orphaned)} orphaned offset_to_symbol entries")
            self._modified = True

    def _check_duplicate_definitions(self, report: dict[str, Any]) -> None:
        """Check for duplicate definitions (same CU + DIE)."""
        for symbol, definitions in self.data.get("symbol_definitions", {}).items():
            seen = set()
            unique_defs = []
            for d in definitions:
                key = (d["cu_offset"], d["die_offset"])
                if key not in seen:
                    seen.add(key)
                    unique_defs.append(d)
                else:
                    report["issues"].append(f"Symbol {symbol} has duplicate definition at CU 0x{d['cu_offset']:x}")

            if len(unique_defs) < len(definitions):
                self.data["symbol_definitions"][symbol] = unique_defs
                report["repairs"].append(f"Removed {len(definitions) - len(unique_defs)} duplicate definitions for {symbol}")
                self._modified = True

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics for monitoring and health checks.

        Returns:
            Dictionary with cache statistics
        """
        multi_def_symbols = [
            s for s, defs in self.data.get("symbol_definitions", {}).items() if len(defs) > 1
        ]

        return {
            "symbols": len(self.data["symbol_to_offset"]),
            "cu_mappings": len(self.data["symbol_to_cu_offset"]),
            "compilation_units": len(self.data["cu_offset_to_symbols"]),
            "multi_definition_symbols": len(multi_def_symbols),
            "total_definitions": sum(len(defs) for defs in self.data.get("symbol_definitions", {}).values()),
            "file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
            "last_updated": self.data.get("last_updated", 0),
            "version": self.data.get("version", "unknown"),
        }

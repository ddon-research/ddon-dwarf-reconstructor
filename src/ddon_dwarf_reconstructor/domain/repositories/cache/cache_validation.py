"""Focused persistent-symbol-cache operations."""

from __future__ import annotations

from typing import Any

from ....infrastructure.logging import get_logger
from .cache_context import CacheContext

logger = get_logger(__name__)


class CacheValidationMixin:
    def validate_and_repair(self: CacheContext) -> dict[str, Any]:
        """Validate cache integrity and attempt automatic repairs.

        Returns:
            Validation report with issues found and repairs made
        """
        report: dict[str, Any] = {
            "valid": True,
            "issues": [],
            "repairs": [],
            "warnings": [],
        }

        # Check for missing required fields
        self._check_required_fields(report)

        # Check consistency between definitions and primary mappings
        self._check_primary_mappings(report)

        # Rebuild CU->symbols mapping if it drifted from symbol_to_cu_offset
        self._check_cu_symbol_mappings(report)

        # Check for orphaned entries
        self._check_orphaned_entries(report)

        # Check for duplicate definitions
        self._check_duplicate_definitions(report)

        if self._modified:
            logger.info(
                f"Cache validation found {len(report['issues'])} issues, made {len(report['repairs'])} repairs"
            )

        return report

    def _check_required_fields(self: CacheContext, report: dict[str, Any]) -> None:
        """Check for missing required fields and add them."""
        required_fields = [
            "symbol_to_offset",
            "symbol_to_cu_offset",
            "symbol_definitions",
            "cu_offset_to_symbols",
        ]
        for field in required_fields:
            if field not in self.data:
                report["issues"].append(f"Missing required field: {field}")
                self.data[field] = {}
                report["repairs"].append(f"Added missing field: {field}")
                self._modified = True
                report["valid"] = False

    def _check_primary_mappings(self: CacheContext, report: dict[str, Any]) -> None:
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

    def _check_cu_symbol_mappings(self: CacheContext, report: dict[str, Any]) -> None:
        """Rebuild CU-to-symbol mappings from primary symbol->CU entries when they drift."""
        expected: dict[str, list[str]] = {}
        for symbol, cu_offset in self.data.get("symbol_to_cu_offset", {}).items():
            cu_key = str(cu_offset)
            expected.setdefault(cu_key, []).append(symbol)

        # Sort for deterministic comparisons and output.
        normalized_expected = {key: sorted(values) for key, values in expected.items()}
        normalized_actual = {
            str(key): sorted(list(values))
            for key, values in self.data.get("cu_offset_to_symbols", {}).items()
        }

        if normalized_expected != normalized_actual:
            report["issues"].append("cu_offset_to_symbols drifted from symbol_to_cu_offset")
            self.data["cu_offset_to_symbols"] = normalized_expected
            report["repairs"].append("Rebuilt cu_offset_to_symbols from primary symbol mappings")
            self._modified = True
            report["valid"] = False

    def _check_orphaned_entries(self: CacheContext, report: dict[str, Any]) -> None:
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

    def _check_duplicate_definitions(self: CacheContext, report: dict[str, Any]) -> None:
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
                    report["issues"].append(
                        f"Symbol {symbol} has duplicate definition at CU 0x{d['cu_offset']:x}"
                    )

            if len(unique_defs) < len(definitions):
                self.data["symbol_definitions"][symbol] = unique_defs
                report["repairs"].append(
                    f"Removed {len(definitions) - len(unique_defs)} duplicate definitions for {symbol}"
                )
                self._modified = True

    def get_statistics(self: CacheContext) -> dict[str, Any]:
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
            "total_definitions": sum(
                len(defs) for defs in self.data.get("symbol_definitions", {}).values()
            ),
            "file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
            "last_updated": self.data.get("last_updated", 0),
            "version": self.data.get("version", "unknown"),
        }

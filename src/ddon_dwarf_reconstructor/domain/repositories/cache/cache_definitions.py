"""Focused persistent-symbol-cache operations."""

from __future__ import annotations

from time import time
from typing import Any

from ....infrastructure.logging import get_logger
from .cache_context import CacheContext

logger = get_logger(__name__)


class CacheDefinitionsMixin:
    def get_symbol_offset(self: CacheContext, symbol_name: str) -> int | None:
        """Get offset for symbol.

        Args:
            symbol_name: Name of symbol

        Returns:
            Symbol offset or None if not found
        """
        result = self.data["symbol_to_offset"].get(symbol_name)
        return int(result) if result is not None else None

    def add_symbol(self: CacheContext, symbol_name: str, offset: int) -> None:
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

    def get_symbol_by_offset(self: CacheContext, offset: int) -> str | None:
        """Get symbol name by offset.

        Args:
            offset: DWARF offset

        Returns:
            Symbol name or None if not found
        """
        result = self.data["offset_to_symbol"].get(str(offset))
        return str(result) if result is not None else None

    def get_symbol_cu_offset(self: CacheContext, symbol_name: str) -> int | None:
        """Get CU offset for symbol for efficient CU targeting.

        Args:
            symbol_name: Name of symbol to look up

        Returns:
            CU offset if found, None otherwise
        """
        result = self.data["symbol_to_cu_offset"].get(symbol_name)
        return int(result) if result is not None else None

    def add_symbol_cu_mapping(
        self: CacheContext,
        symbol_name: str,
        cu_offset: int,
        die_offset: int,
        score: int = 0,
        complete: bool = True,
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
            (
                d
                for d in definitions
                if d["cu_offset"] == cu_offset and d["die_offset"] == die_offset
            ),
            None,
        )

        if existing:
            # Update score if new score is higher (better definition found)
            if score > existing["score"]:
                existing["score"] = score
                existing["complete"] = complete
                logger.debug(
                    f"Updated {symbol_name} definition at CU 0x{cu_offset:x} with score {score}"
                )
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

    def get_cu_symbols(self: CacheContext, cu_offset: int) -> list[str]:
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

    def _get_definition_records(self: CacheContext, symbol_name: str) -> list[dict[str, Any]]:
        """Return JSON definition records with a stable dictionary shape."""
        raw_definitions = self.data.get("symbol_definitions", {})
        if not isinstance(raw_definitions, dict):
            return []

        definitions = raw_definitions.get(symbol_name, [])
        if not isinstance(definitions, list):
            return []

        records: list[dict[str, Any]] = []
        for definition in definitions:
            if isinstance(definition, dict):
                records.append({str(key): value for key, value in definition.items()})
        return records

    def _get_best_definition(self: CacheContext, symbol_name: str) -> dict[str, Any] | None:
        """Get best definition for symbol (highest score complete definition).

        Args:
            symbol_name: Symbol name to look up

        Returns:
            Best definition dict or None if no definitions exist
        """
        definitions = self._get_definition_records(symbol_name)
        if not definitions:
            return None

        # Prefer complete definitions with highest score
        complete_defs = [d for d in definitions if d.get("complete", True)]
        if complete_defs:
            return max(complete_defs, key=lambda d: d.get("score", 0))

        # Fallback to incomplete definition with highest score
        return max(definitions, key=lambda d: d.get("score", 0))

    def get_all_definitions(self: CacheContext, symbol_name: str) -> list[dict[str, Any]]:
        """Get all definitions for a symbol across different CUs.

        Args:
            symbol_name: Symbol name to look up

        Returns:
            List of definition dicts, sorted by score (descending)
        """
        definitions = self._get_definition_records(symbol_name)
        return sorted(definitions, key=lambda d: d.get("score", 0), reverse=True)

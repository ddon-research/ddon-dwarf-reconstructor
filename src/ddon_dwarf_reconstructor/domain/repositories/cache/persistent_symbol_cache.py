#!/usr/bin/env python3

"""Persistent symbol cache for DWARF parsing."""

import json
from pathlib import Path
from time import time
from typing import Any, cast

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
        self.data = self._load_cache()
        self._modified = False
    
    def _load_cache(self) -> dict[str, Any]:
        """Load cached mappings from disk.
        
        Returns:
            Cache data dictionary
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded cache from {self.cache_file} "
                              f"({len(data.get('symbol_to_offset', {}))} symbols)")
                    # Migrate old cache format to new format
                    return self._migrate_cache_format(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}")
        
        # Return empty cache structure
        return self._create_empty_cache()
    
    def _create_empty_cache(self) -> dict[str, Any]:
        """Create empty cache structure with current format.
        
        Returns:
            Empty cache dictionary
        """
        return {
            "version": "1.1",  # Current version with CU mapping support
            "elf_hash": None,
            "symbol_to_offset": {},
            "offset_to_symbol": {},
            "symbol_to_cu_offset": {},  # NEW: symbol -> CU offset mapping
            "cu_offset_to_symbols": {},  # NEW: CU offset -> symbols list mapping
            "typedef_offsets": {},
            "class_offsets": {},
            "created": time(),
            "last_updated": time()
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
        
        # Clean up any duplicate keys that might exist from JSON parsing issues
        data = self._cleanup_duplicate_keys(data)
        
        return data
    
    def _cleanup_duplicate_keys(self, data: dict[str, Any]) -> dict[str, Any]:
        """Clean up duplicate keys in cu_offset_to_symbols.
        
        Args:
            data: Cache data that may contain duplicate keys
            
        Returns:
            Cleaned cache data with merged lists for duplicate keys
        """
        # The cu_offset_to_symbols section is the one that can have duplicate keys
        cu_symbols = data.get("cu_offset_to_symbols", {})
        
        # Since JSON parsing only keeps the last value for duplicate keys,
        # we need to reconstruct this mapping from the other mappings
        if cu_symbols:
            # Rebuild cu_offset_to_symbols from symbol_to_cu_offset to ensure consistency
            symbol_to_cu = data.get("symbol_to_cu_offset", {})
            symbol_to_offset = data.get("symbol_to_offset", {})
            
            # Build a proper mapping without duplicates
            rebuilt_cu_symbols: dict[int, list[str]] = {}
            
            for symbol, cu_offset in symbol_to_cu.items():
                # Find all full symbol keys (with type prefix) for this symbol
                matching_keys = []
                for key in symbol_to_offset:
                    if key.endswith(f":{symbol}") or key == symbol:
                        matching_keys.append(key)
                
                # Add all matching keys to the CU mapping
                for full_key in matching_keys:
                    if cu_offset not in rebuilt_cu_symbols:
                        rebuilt_cu_symbols[cu_offset] = []
                    if full_key not in rebuilt_cu_symbols[cu_offset]:
                        rebuilt_cu_symbols[cu_offset].append(full_key)
            
            # Convert back to string keys for JSON compatibility
            data["cu_offset_to_symbols"] = {str(k): v for k, v in rebuilt_cu_symbols.items()}
            
            if rebuilt_cu_symbols:
                logger.info(f"Cleaned up duplicate CU keys, rebuilt "
                           f"{len(rebuilt_cu_symbols)} CU mappings")
                self._modified = True
        
        return data
    
    def get_elf_hash(self) -> str | None:
        """Get stored ELF file hash.
        
        Returns:
            Stored ELF hash or None
        """
        return self.data.get("elf_hash")
    
    def set_elf_hash(self, elf_hash: str) -> None:
        """Set ELF file hash.
        
        Args:
            elf_hash: Hash of ELF file
        """
        if self.data.get("elf_hash") != elf_hash:
            self.data["elf_hash"] = elf_hash
            self._modified = True
    
    def get_symbol_offset(self, symbol_name: str, symbol_type: str = "") -> int | None:
        """Get offset for symbol.
        
        Args:
            symbol_name: Name of symbol
            symbol_type: Type prefix (e.g., "class", "typedef")
            
        Returns:
            Symbol offset or None if not found
        """
        key = f"{symbol_type}:{symbol_name}" if symbol_type else symbol_name
        return self.data["symbol_to_offset"].get(key)
    
    def add_symbol(self, symbol_name: str, offset: int, symbol_type: str = "") -> None:
        """Add symbol→offset mapping.
        
        Args:
            symbol_name: Name of symbol
            offset: DWARF offset
            symbol_type: Type prefix (e.g., "class", "typedef")
        """
        key = f"{symbol_type}:{symbol_name}" if symbol_type else symbol_name
        
        if key not in self.data["symbol_to_offset"]:
            self.data["symbol_to_offset"][key] = offset
            self.data["offset_to_symbol"][offset] = key
            self.data["last_updated"] = time()
            self._modified = True
            
            # Add to type-specific index
            if symbol_type == "typedef":
                self.data["typedef_offsets"][symbol_name] = offset
            elif symbol_type == "class":
                self.data["class_offsets"][symbol_name] = offset
    
    def get_symbol_by_offset(self, offset: int) -> str | None:
        """Get symbol name by offset.
        
        Args:
            offset: DWARF offset
            
        Returns:
            Symbol name or None if not found
        """
        return self.data["offset_to_symbol"].get(offset)
    
    def save(self) -> None:
        """Save cache to disk if modified."""
        if self._modified:
            try:
                # Clean up any duplicate keys before saving
                self.data = self._cleanup_duplicate_keys(self.data)
                
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
                logger.info(f"Saved cache to {self.cache_file} "
                          f"({len(self.data['symbol_to_offset'])} symbols)")
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
        return self.data["symbol_to_cu_offset"].get(symbol_name)
    
    def add_symbol_cu_mapping(self, symbol_key: str, cu_offset: int, die_offset: int) -> None:
        """Add symbol to CU offset mapping for efficient targeting.
        
        Args:
            symbol_key: Symbol key with type prefix (e.g., "class:MtObject", "typedef:u32")
            cu_offset: Offset of compilation unit containing the symbol
            die_offset: Offset of DIE within the CU
        """
        
        # Store both CU and DIE mappings using the full key
        self.data["symbol_to_offset"][symbol_key] = die_offset
        self.data["offset_to_symbol"][die_offset] = symbol_key
        
        # Extract symbol name and type from key
        if ":" in symbol_key:
            symbol_type, symbol_name = symbol_key.split(":", 1)
            
            # Store CU mapping using the symbol name for targeted search compatibility
            self.data["symbol_to_cu_offset"][symbol_name] = cu_offset
            
            # Track symbols per CU using the full key to maintain consistency
            cu_symbols = self.data["cu_offset_to_symbols"].setdefault(cu_offset, [])
            if symbol_key not in cu_symbols:
                cu_symbols.append(symbol_key)
            
            # Update type-specific indexes
            if symbol_type == "typedef":
                self.data["typedef_offsets"][symbol_name] = die_offset
            elif symbol_type == "class":
                self.data["class_offsets"][symbol_name] = die_offset
        else:
            # Fallback for keys without type prefix
            self.data["symbol_to_cu_offset"][symbol_key] = cu_offset
            cu_symbols = self.data["cu_offset_to_symbols"].setdefault(cu_offset, [])
            if symbol_key not in cu_symbols:
                cu_symbols.append(symbol_key)
        
        self.data["last_updated"] = time()
        self._modified = True

    def get_cu_symbols(self, cu_offset: int) -> list[str]:
        """Get all symbols known to be in a specific CU.
        
        Args:
            cu_offset: Offset of compilation unit
            
        Returns:
            List of symbol names in the CU
        """
        return self.data["cu_offset_to_symbols"].get(cu_offset, [])

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "symbols": len(self.data["symbol_to_offset"]),
            "cu_mappings": len(self.data["symbol_to_cu_offset"]),
            "compilation_units": len(self.data["cu_offset_to_symbols"]),
            "typedefs": len(self.data["typedef_offsets"]),
            "classes": len(self.data["class_offsets"]),
            "file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
            "last_updated": self.data.get("last_updated", 0)
        }


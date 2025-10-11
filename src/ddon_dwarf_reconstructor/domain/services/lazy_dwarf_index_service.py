#!/usr/bin/env python3

"""Lazy DWARF index service for memory-efficient symbol lookups."""

import hashlib
from time import time
from typing import Any

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ...infrastructure.logging import get_logger, log_timing
from ..repositories.cache import LRUCache, PersistentSymbolCache

logger = get_logger(__name__)


class LazyDwarfIndexService:
    """Manages offset-based DWARF lookups with persistent caching.
    
    This class provides memory-efficient DWARF symbol resolution by:
    1. Using offset-based DIE caching instead of loading all DIEs
    2. Maintaining persistent symbol→offset mappings
    3. Implementing LRU caches with configurable limits
    4. Providing fallback to targeted scanning when needed
    """

    def __init__(self, dwarf_info: DWARFInfo, cache_file: str = ".dwarf_cache.json",
                 die_cache_size: int = 10000, type_cache_size: int = 5000):
        """Initialize lazy DWARF index.
        
        Args:
            dwarf_info: DWARF information from pyelftools
            cache_file: Path to persistent cache file
            die_cache_size: Maximum DIEs to cache in memory
            type_cache_size: Maximum type resolutions to cache
        """
        self.dwarf_info = dwarf_info
        self.persistent_cache = PersistentSymbolCache(cache_file)

        # Runtime caches (LRU with limits)
        self.die_cache = LRUCache(die_cache_size)
        self.type_cache = LRUCache(type_cache_size)

        # Track discovered symbols for incremental cache updates
        self._discovered_symbols: set[str] = set()

        logger.info(f"Initialized LazyDwarfIndexService with die_cache={die_cache_size}, "
                   f"type_cache={type_cache_size}")

    def get_elf_hash(self, elf_file_path: str) -> str:
        """Calculate hash of ELF file for cache validation.
        
        Args:
            elf_file_path: Path to ELF file
            
        Returns:
            SHA256 hash of ELF file
        """
        try:
            with open(elf_file_path, 'rb') as f:
                # Hash first 64KB for performance (headers contain most structural info)
                data = f.read(65536)
                return hashlib.sha256(data).hexdigest()[:16]  # First 16 chars
        except OSError:
            return ""

    def validate_cache(self, elf_file_path: str) -> bool:
        """Validate that persistent cache matches current ELF file.
        
        Args:
            elf_file_path: Path to ELF file
            
        Returns:
            True if cache is valid, False otherwise
        """
        current_hash = self.get_elf_hash(elf_file_path)
        stored_hash = self.persistent_cache.get_elf_hash()

        if stored_hash != current_hash:
            logger.info(f"ELF file changed (hash: {stored_hash} → {current_hash}), "
                       "cache will be rebuilt")
            self.persistent_cache.data = {
                "version": "1.0",
                "elf_hash": current_hash,
                "symbol_to_offset": {},
                "offset_to_symbol": {},
                "typedef_offsets": {},
                "class_offsets": {},
                "created": time(),
                "last_updated": time()
            }
            self.persistent_cache.set_elf_hash(current_hash)
            return False

        return True

    def find_symbol_offset(self, symbol_name: str, symbol_type: str = "") -> int | None:
        """Find offset for symbol using persistent cache.
        
        Args:
            symbol_name: Name of symbol to find
            symbol_type: Type of symbol (e.g., "class", "typedef")
            
        Returns:
            DWARF offset of symbol or None if not found
        """
        return self.persistent_cache.get_symbol_offset(symbol_name, symbol_type)

    def get_die_by_offset(self, offset: int) -> DIE | None:
        """Get DIE by DWARF offset with caching.
        
        Args:
            offset: DWARF offset of DIE
            
        Returns:
            DIE object or None if not found
        """
        # Check cache first
        cached_die = self.die_cache.get(offset)
        if cached_die is not None:
            return cached_die

        # Find DIE using pyelftools
        die = self._find_die_at_offset(offset)
        if die is not None:
            self.die_cache.put(offset, die)

        return die

    def _find_die_at_offset(self, offset: int) -> DIE | None:
        """Find DIE at specific offset using pyelftools.
        
        This is the fallback method when DIE is not cached.
        Uses targeted CU lookup when possible.
        
        Args:
            offset: DWARF offset to find
            
        Returns:
            DIE at offset or None if not found
        """
        try:
            logger.debug(f"Searching for DIE at offset 0x{offset:x}")
            if not self.dwarf_info:
                logger.error("DWARF info is None!")
                return None
            logger.debug("DWARF info is available, starting CU iteration")
            # Try to find which CU contains this offset
            for cu in self.dwarf_info.iter_CUs():
                cu_start = cu.cu_offset
                cu_end = cu_start + cu.header.unit_length
                logger.debug(f"Checking CU 0x{cu_start:x}-0x{cu_end:x}")

                if cu_start <= offset < cu_end:
                    logger.debug(f"Found target CU for offset 0x{offset:x}: 0x{cu_start:x}-0x{cu_end:x}")
                    # Found the right CU, now find the DIE
                    for die in cu.iter_DIEs():
                        if die.offset == offset:
                            logger.debug(f"Found DIE at offset 0x{offset:x}: {die.tag}")
                            return die
                    logger.debug("DIE not found in CU despite being in range")
                    break

            logger.warning(f"DIE not found at offset 0x{offset:x}")
            return None

        except Exception as e:
            logger.error(f"Error finding DIE at offset 0x{offset:x}: {e}")
            return None

    def _get_default_target_types(self) -> set[str]:
        """Get default set of DIE tags to discover."""
        return {
            "DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type",
            "DW_TAG_typedef", "DW_TAG_enumeration_type"
        }

    def _get_symbol_type(self, die_tag: str) -> str:
        """Determine symbol type from DIE tag."""
        if die_tag == "DW_TAG_typedef":
            return "typedef"
        elif die_tag in ("DW_TAG_class_type", "DW_TAG_structure_type"):
            return "class"
        elif die_tag == "DW_TAG_namespace":
            return "namespace"
        else:
            return "type"

    def _extract_symbol_name(self, name_attr: Any) -> str:
        """Extract symbol name from DIE name attribute."""
        if isinstance(name_attr.value, bytes):
            return name_attr.value.decode("utf-8")
        return str(name_attr.value)

    def _process_die_symbol(self, die: DIE, cu_offset: int | None = None) -> bool:
        """Process a single DIE for symbol discovery.
        
        Args:
            die: DIE to process
            cu_offset: Optional CU offset for improved caching
        
        Returns:
            True if symbol was discovered and cached
        """
        name_attr = die.attributes.get("DW_AT_name")
        if not name_attr:
            return False

        symbol_name = self._extract_symbol_name(name_attr)
        symbol_type = self._get_symbol_type(die.tag)

        # Add to persistent cache with consistent key format (always with type prefix)
        symbol_key = f"{symbol_type}:{symbol_name}" if symbol_type else symbol_name
        if cu_offset is not None:
            self.persistent_cache.add_symbol_cu_mapping(symbol_key, cu_offset, die.offset)
        else:
            self.persistent_cache.add_symbol(symbol_name, die.offset, symbol_type)

        self._discovered_symbols.add(f"{symbol_type}:{symbol_name}")

        logger.debug(f"Discovered {symbol_type} '{symbol_name}' at 0x{die.offset:x}")
        return True

    @log_timing
    def discover_symbols_in_cu(self, cu: CompileUnit, target_types: set[str] | None = None) -> int:
        """Discover and cache symbols in a compilation unit.
        
        Args:
            cu: Compilation unit to scan
            target_types: Set of DIE tags to look for (None = all types)
            
        Returns:
            Number of symbols discovered
        """
        if target_types is None:
            target_types = self._get_default_target_types()

        discovered = 0

        try:
            for die in cu.iter_DIEs():
                if die.tag in target_types and self._process_die_symbol(die, cu.cu_offset):
                    discovered += 1

        except Exception as e:
            logger.error(f"Error discovering symbols in CU at 0x{cu.cu_offset:x}: {e}")

        return discovered

    @log_timing
    def targeted_symbol_search(self, symbol_name: str, symbol_type: str = "") -> int | None:
        """Search for symbol using targeted CU scanning.
        
        This is used as fallback when symbol is not in persistent cache.
        Now optimized to check for CU-level hints first.
        
        Args:
            symbol_name: Name of symbol to find
            symbol_type: Type of symbol to search for
            
        Returns:
            DWARF offset of symbol or None if not found
        """
        logger.info(f"Performing targeted search for {symbol_type}:{symbol_name}")

        # Check if we have a CU hint for this symbol
        cu_offset = self.persistent_cache.get_symbol_cu_offset(symbol_name)

        # Determine target DIE tags based on symbol type
        if symbol_type == "typedef":
            target_tags = {"DW_TAG_typedef"}
        elif symbol_type == "class":
            target_tags = {"DW_TAG_class_type", "DW_TAG_structure_type"}
        elif symbol_type == "namespace":
            target_tags = {"DW_TAG_namespace"}
        elif symbol_type == "base_type":
            target_tags = {"DW_TAG_base_type"}
        elif symbol_type == "primitive_type":
            # Search for both typedef and base_type simultaneously for primitives
            target_tags = {"DW_TAG_typedef", "DW_TAG_base_type"}
        else:
            target_tags = {
                "DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type",
                "DW_TAG_typedef", "DW_TAG_enumeration_type", "DW_TAG_base_type",
                "DW_TAG_namespace"
            }

        target_name = symbol_name.encode("utf-8")

        try:
            # If we have a CU hint, search that CU first (fast path)
            if cu_offset is not None:
                logger.debug(f"Using CU hint: searching CU at 0x{cu_offset:x} first")
                target_cu = self._get_cu_by_offset(cu_offset)
                if target_cu:
                    result = self._search_cu_for_symbol(
                        target_cu, symbol_name, target_tags, target_name, symbol_type
                    )
                    if result:
                        return result
                    logger.debug("Symbol not found in hinted CU, falling back to full search")

            # Fallback to full CU iteration (slow path)
            logger.debug("Performing full CU scan (no CU hint available)")
            for cu in self.dwarf_info.iter_CUs():
                # Skip CU we already checked
                if cu_offset is not None and cu.cu_offset == cu_offset:
                    continue

                result = self._search_cu_for_symbol(
                    cu, symbol_name, target_tags, target_name, symbol_type
                )
                if result:
                    return result

        except Exception as e:
            logger.error(f"Error in targeted search for {symbol_name}: {e}")

        logger.warning(f"Symbol {symbol_type}:{symbol_name} not found")
        return None

    def _get_cu_by_offset(self, cu_offset: int) -> CompileUnit | None:
        """Get compilation unit by its offset.
        
        Args:
            cu_offset: Offset of the compilation unit
            
        Returns:
            CompileUnit object or None if not found
        """
        try:
            for cu in self.dwarf_info.iter_CUs():
                if cu.cu_offset == cu_offset:
                    return cu
        except Exception as e:
            logger.error(f"Error finding CU at offset 0x{cu_offset:x}: {e}")
        return None

    def _search_cu_for_symbol(self, cu: CompileUnit, symbol_name: str, target_tags: set[str],
                             target_name: bytes, symbol_type: str) -> int | None:
        """Search a specific CU for a symbol.
        
        Args:
            cu: Compilation unit to search
            symbol_name: Name of symbol to find
            target_tags: Set of DIE tags to match
            target_name: Encoded symbol name for comparison
            symbol_type: Type of symbol for caching
            
        Returns:
            DIE offset if found, None otherwise
        """
        try:
            for die in cu.iter_DIEs():
                if die.tag in target_tags:
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr and name_attr.value == target_name:
                        # Found it! Determine actual type for caching
                        if symbol_type == "primitive_type":
                            # Map actual DIE tag to our type system
                            if die.tag == "DW_TAG_typedef":
                                actual_type = "typedef"
                            elif die.tag == "DW_TAG_base_type":
                                actual_type = "base_type"
                            else:
                                actual_type = ""
                        else:
                            actual_type = symbol_type

                        # Add to cache with proper key format
                        symbol_key = f"{actual_type}:{symbol_name}" if actual_type else symbol_name
                        self.persistent_cache.add_symbol_cu_mapping(
                            symbol_key, cu.cu_offset, die.offset
                        )
                        logger.info(f"Found {actual_type}:{symbol_name} at 0x{die.offset:x} "
                                   f"in CU 0x{cu.cu_offset:x}")
                        return die.offset
        except Exception as e:
            logger.error(f"Error searching CU 0x{cu.cu_offset:x} for {symbol_name}: {e}")

        return None

    def save_cache(self) -> None:
        """Save persistent cache to disk."""
        self.persistent_cache.save()

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics about caches and performance.
        
        Returns:
            Dictionary with cache and performance statistics
        """
        return {
            "die_cache": self.die_cache.stats(),
            "type_cache": self.type_cache.stats(),
            "persistent_cache": self.persistent_cache.get_statistics(),
            "discovered_symbols": len(self._discovered_symbols)
        }

    def clear_runtime_caches(self) -> None:
        """Clear runtime caches (DIE and type caches)."""
        self.die_cache.clear()
        self.type_cache.clear()
        logger.info("Runtime caches cleared")


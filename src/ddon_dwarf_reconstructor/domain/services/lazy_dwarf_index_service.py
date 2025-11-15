#!/usr/bin/env python3

"""Lazy DWARF index service for memory-efficient symbol lookups."""

import hashlib
from typing import Any

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ...infrastructure.logging import get_logger, log_timing
from ..models.dwarf.tag_registry import DwarfTagRegistry
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

    def __init__(
        self,
        dwarf_info: DWARFInfo,
        cache_file: str = ".dwarf_cache.json",
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
    ):
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

        logger.info(
            f"Initialized LazyDwarfIndexService with die_cache={die_cache_size}, "
            f"type_cache={type_cache_size}"
        )

    def get_elf_hash(self, elf_file_path: str) -> str:
        """Calculate hash of ELF file for cache validation.

        Args:
            elf_file_path: Path to ELF file

        Returns:
            SHA256 hash of ELF file
        """
        try:
            with open(elf_file_path, "rb") as f:
                # Hash first 64KB for performance (headers contain most structural info)
                data = f.read(65536)
                return hashlib.sha256(data).hexdigest()[:16]  # First 16 chars
        except OSError:
            return ""

    def find_symbol_offset(self, symbol_name: str) -> int | None:
        """Find offset for symbol using persistent cache.

        Args:
            symbol_name: Name of symbol to find

        Returns:
            DWARF offset of symbol or None if not found
        """
        return self.persistent_cache.get_symbol_offset(symbol_name)

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
                    logger.debug(
                        f"Found target CU for offset 0x{offset:x}: 0x{cu_start:x}-0x{cu_end:x}"
                    )
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
        return set(DwarfTagRegistry.ALL_SEARCHABLE_TAGS)

    def _get_symbol_type(self, die_tag: str) -> str:
        """Determine symbol type from DIE tag using centralized registry."""
        # Use registry for consistent mapping
        if DwarfTagRegistry.is_searchable_tag(die_tag):
            return die_tag  # Use the tag itself as the type identifier
        else:
            return "DW_TAG_other"

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

        # Add to persistent cache using clean symbol name (no prefix)
        if cu_offset is not None:
            self.persistent_cache.add_symbol_cu_mapping(symbol_name, cu_offset, die.offset)
        else:
            self.persistent_cache.add_symbol(symbol_name, die.offset)

        self._discovered_symbols.add(symbol_name)

        logger.debug(f"Discovered '{symbol_name}' at 0x{die.offset:x} (tag: {die.tag})")
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
    def targeted_symbol_search(self, symbol_name: str, timeout: float = 180.0) -> int | None:
        """Search for symbol using targeted CU scanning with scoring.

        This is used as fallback when symbol is not in persistent cache.
        Searches across compilation units and prefers complete definitions
        over forward declarations. Includes timeout protection to prevent
        indefinite searches for types lacking debug information.

        Args:
            symbol_name: Name of symbol to find
            timeout: Maximum search time in seconds (default: 180s)

        Returns:
            DWARF offset of best match or None if not found/timed out
        """
        import time
        
        logger.info(f"Performing targeted search for {symbol_name}")
        
        start_time = time.time()
        timed_out = False

        # Check if we have a CU hint for this symbol
        cu_offset_hint = self.persistent_cache.get_symbol_cu_offset(symbol_name)

        # Search for all known DWARF tag types
        target_tags = set(DwarfTagRegistry.ALL_SEARCHABLE_TAGS)

        target_name = symbol_name.encode("utf-8")
        
        # Track best match across all CUs
        global_best_offset = None
        global_best_score = -1
        global_best_cu = None
        fallback_offset = None
        cus_searched = 0

        try:
            # If we have a CU hint, search that CU first (fast path)
            if cu_offset_hint is not None:
                logger.debug(f"Using CU hint: searching CU at 0x{cu_offset_hint:x} first")
                target_cu = self._get_cu_by_offset(cu_offset_hint)
                if target_cu:
                    result_offset, score = self._search_cu_for_symbol_with_score(
                        target_cu, symbol_name, target_tags, target_name
                    )
                    if result_offset:
                        cus_searched += 1
                        # Check if it's a perfect match
                        if score >= 10000:  # Has members + size
                            logger.info(
                                f"Found {symbol_name} at 0x{result_offset:x} in CU 0x{cu_offset_hint:x} "
                                f"(perfect match: score={score})"
                            )
                            return result_offset
                        
                        # Save as best candidate
                        global_best_offset = result_offset
                        global_best_score = score
                        global_best_cu = cu_offset_hint
                        
                        if fallback_offset is None:
                            fallback_offset = result_offset
                    
                    logger.debug(
                        f"Found candidate in hinted CU with score={score}. "
                        f"Continuing search for better definition."
                    )

            # Search remaining CUs for better matches
            logger.debug("Performing full CU scan to find best definition")
            for cu in self.dwarf_info.iter_CUs():
                # Check timeout at start of each CU
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    timed_out = True
                    logger.error(
                        f"Targeted search for '{symbol_name}' timed out after {elapsed:.1f}s. "
                        f"Searched {cus_searched} CUs. Best score so far: {global_best_score}. "
                        f"Type may lack debug information or be located very late in ELF."
                    )
                    break
                
                # Skip CU we already checked
                if cu_offset_hint is not None and cu.cu_offset == cu_offset_hint:
                    continue

                cus_searched += 1
                
                # Check timeout before expensive CU search
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    timed_out = True
                    logger.error(
                        f"Targeted search for '{symbol_name}' timed out after {elapsed:.1f}s. "
                        f"Searched {cus_searched} CUs. Best score so far: {global_best_score}."
                    )
                    break
                
                result_offset, score = self._search_cu_for_symbol_with_score(
                    cu, symbol_name, target_tags, target_name
                )
                if result_offset:
                    # Check if this is a better match
                    if score > global_best_score:
                        global_best_offset = result_offset
                        global_best_score = score
                        global_best_cu = cu.cu_offset
                        
                        logger.debug(
                            f"Found better candidate at 0x{result_offset:x} in CU 0x{cu.cu_offset:x} "
                            f"with score={score}"
                        )
                    
                    # Save first match as fallback
                    if fallback_offset is None:
                        fallback_offset = result_offset
                    
                    # Early exit for good matches:
                    # - Classes with members (score >= 10000)
                    # - Typedefs and base types (score >= 5000)
                    # - Complete enums (score >= 6000)
                    if score >= 5000:
                        logger.info(
                            f"Found {symbol_name} at 0x{result_offset:x} in CU 0x{cu.cu_offset:x} "
                            f"(complete definition: score={score})"
                        )
                        self.persistent_cache.add_symbol_cu_mapping(
                            symbol_name, cu.cu_offset, result_offset
                        )
                        return result_offset
            
            # Return best match found
            if global_best_offset and global_best_score > 0:
                logger.info(
                    f"Found {symbol_name} at 0x{global_best_offset:x} in CU 0x{global_best_cu:x} "
                    f"(best match after searching {cus_searched} CUs: score={global_best_score})"
                )
                self.persistent_cache.add_symbol_cu_mapping(
                    symbol_name, global_best_cu, global_best_offset
                )
                return global_best_offset
            
            # Return partial result if timed out
            if timed_out and fallback_offset:
                logger.warning(
                    f"Returning partial result for {symbol_name} after timeout: "
                    f"offset=0x{fallback_offset:x}, score={global_best_score}"
                )
                return fallback_offset
            
            # Warn if only forward declaration found
            if fallback_offset:
                logger.warning(
                    f"Found {symbol_name} at 0x{fallback_offset:x} "
                    f"but only as forward declaration (score={global_best_score}). "
                    f"Complete definition not found after searching {cus_searched} CUs."
                )
                # Don't cache forward declarations - let full scan handle it
                return None

        except Exception as e:
            logger.error(f"Error in targeted search for {symbol_name}: {e}")

        logger.warning(f"Symbol {symbol_name} not found after searching {cus_searched} CUs")
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

    def _search_cu_for_symbol(
        self, cu: CompileUnit, symbol_name: str, target_tags: set[str], target_name: bytes
    ) -> int | None:
        """Search a specific CU for a symbol, preferring complete definitions.

        Uses scoring algorithm to prefer complete class definitions over forward
        declarations when multiple matches exist in the same CU.

        Args:
            cu: Compilation unit to search
            symbol_name: Name of symbol to find
            target_tags: Set of DIE tags to match
            target_name: Encoded symbol name for comparison

        Returns:
            DIE offset if found, None otherwise
        """
        offset, _ = self._search_cu_for_symbol_with_score(cu, symbol_name, target_tags, target_name)
        return offset
    
    def _search_cu_for_symbol_with_score(
        self, cu: CompileUnit, symbol_name: str, target_tags: set[str], target_name: bytes
    ) -> tuple[int | None, int]:
        """Search a specific CU for a symbol and return offset with completeness score.

        Uses scoring algorithm to prefer complete class definitions over forward
        declarations when multiple matches exist in the same CU.

        Args:
            cu: Compilation unit to search
            symbol_name: Name of symbol to find
            target_tags: Set of DIE tags to match
            target_name: Encoded symbol name for comparison

        Returns:
            Tuple of (DIE offset, completeness score) if found, (None, -1) otherwise
        """
        best_offset = None
        best_score = -1
        fallback_offset = None

        try:
            for die in cu.iter_DIEs():
                if die.tag in target_tags:
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr and name_attr.value == target_name:
                        # Found a match - evaluate completeness
                        decl_attr = die.attributes.get("DW_AT_declaration")
                        is_declaration = decl_attr is not None
                        
                        size_attr = die.attributes.get("DW_AT_byte_size")
                        has_size = size_attr and size_attr.value > 0
                        has_members = die.has_children
                        
                        # Calculate completeness score (same as class_parser)
                        # Special handling for different DIE types:
                        # - Typedefs, enums: complete if not declarations (score based on type)
                        # - Classes/structs: prefer those with members and size
                        # - Base types: always complete (high score)
                        score = 0
                        
                        if is_declaration:
                            score = -1000  # Forward declaration
                        elif die.tag == "DW_TAG_typedef":
                            # Typedefs are complete if they have a DW_AT_type attribute
                            type_attr = die.attributes.get("DW_AT_type")
                            if type_attr:
                                score = 5000  # Complete typedef (mid-priority)
                            else:
                                score = -500  # Incomplete typedef
                        elif die.tag == "DW_TAG_base_type":
                            # Base types are always complete
                            score = 8000  # High priority for base types
                        elif die.tag == "DW_TAG_enumeration_type":
                            # Enums are complete if they have size
                            if has_size:
                                score = 6000  # Complete enum
                            else:
                                score = -500  # Incomplete enum
                        else:
                            # Classes/structs/unions: use member-based scoring
                            if has_size:
                                score += size_attr.value if size_attr else 0
                            if has_members:
                                score += 10000
                        
                        logger.debug(
                            f"Found candidate {symbol_name} at 0x{die.offset:x}: "
                            f"score={score}, size={size_attr.value if size_attr else 0}, "
                            f"has_children={has_members}, is_declaration={is_declaration}, "
                            f"tag={die.tag}"
                        )
                        
                        # Track best match
                        if score > best_score:
                            best_score = score
                            best_offset = die.offset
                        
                        # Keep first match as fallback
                        if fallback_offset is None:
                            fallback_offset = die.offset
                        
                        # Early exit optimization for perfect matches
                        # Classes with members, or typedefs/base types
                        if (has_members and has_size and not is_declaration) or score >= 5000:
                            logger.info(
                                f"Found {symbol_name} at 0x{die.offset:x} in CU 0x{cu.cu_offset:x} "
                                f"(perfect match: score={score})"
                            )
                            self.persistent_cache.add_symbol_cu_mapping(
                                symbol_name, cu.cu_offset, die.offset
                            )
                            return die.offset, score
            
            # Return best match found
            if best_offset and best_score > 0:
                logger.info(
                    f"Found {symbol_name} at 0x{best_offset:x} in CU 0x{cu.cu_offset:x} "
                    f"(best match: score={best_score})"
                )
                self.persistent_cache.add_symbol_cu_mapping(
                    symbol_name, cu.cu_offset, best_offset
                )
                return best_offset, best_score
            
            # Return forward declaration with negative score
            if fallback_offset:
                logger.debug(
                    f"Found {symbol_name} at 0x{fallback_offset:x} in CU 0x{cu.cu_offset:x} "
                    f"but only as forward declaration (score={best_score})"
                )
                return fallback_offset, best_score

        except Exception as e:
            logger.error(f"Error searching CU 0x{cu.cu_offset:x} for {symbol_name}: {e}")

        return None, -1

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
            "discovered_symbols": len(self._discovered_symbols),
        }

    def clear_runtime_caches(self) -> None:
        """Clear runtime caches (DIE and type caches)."""
        self.die_cache.clear()
        self.type_cache.clear()
        logger.info("Runtime caches cleared")

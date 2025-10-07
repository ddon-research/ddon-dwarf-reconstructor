"""Utility for extracting and searching DIEs from DWARF information."""

import logging
import pickle
import time
from hashlib import sha256
from pathlib import Path
from typing import Callable, Optional

from .models import CompilationUnit, DIE

logger = logging.getLogger(__name__)


class DIEExtractor:
    """Extracts and searches Debug Information Entries from compilation units.

    Performance optimizations based on Ghidra DWARF parser insights:
    - Lazy index building: Indexes built on-demand, cached for reuse
    - Symbol name index: Maps symbol names to (CU index, DIE) for fast lookup
    - Tag index: Maps DWARF tags to DIEs for type searches
    - Type-specific index: Optimized index for class/struct lookups only
    - Early-exit searches: Stop immediately when target found (for single-result methods)
    """

    def __init__(
        self,
        compilation_units: list[CompilationUnit],
        elf_file_path: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        incremental: bool = False,
    ) -> None:
        """
        Initialize the DIE extractor.

        Args:
            compilation_units: List of parsed compilation units
            elf_file_path: Path to ELF file for cache key generation
            cache_dir: Directory for index cache files (default: .dwarf_cache)
            incremental: Enable incremental index building (can add CUs dynamically)
        """
        self.compilation_units = compilation_units
        self.elf_file_path = elf_file_path
        self.cache_dir = cache_dir or Path(".dwarf_cache")
        self.incremental = incremental

        # Lazy-loaded indexes (built on first use, cached thereafter)
        self._name_index: Optional[dict[str, list[tuple[int, DIE]]]] = None
        self._tag_index: Optional[dict[str, list[tuple[int, DIE]]]] = None
        self._offset_index: Optional[dict[int, tuple[int, DIE]]] = None

        # Type-specific indexes for performance optimization
        self._type_name_index: Optional[dict[str, tuple[int, DIE]]] = None
        self._all_type_names: Optional[set[str]] = None

        # Track which CUs have been indexed (for incremental mode)
        self._indexed_cu_count: int = 0

    def _build_name_index(self) -> None:
        """Build the symbol name index mapping names to (CU index, DIE) tuples.

        This is a lazy operation - only called once on first name search.
        Subsequent searches reuse the cached index.
        """
        if self._name_index is not None:
            return

        self._name_index = {}
        for cu_idx, cu in enumerate(self.compilation_units):
            for die in cu.dies:
                name = die.get_name()
                if name:
                    if name not in self._name_index:
                        self._name_index[name] = []
                    self._name_index[name].append((cu_idx, die))

    def _build_tag_index(self) -> None:
        """Build the tag index mapping DWARF tags to (CU index, DIE) tuples.

        This is a lazy operation - only called once on first tag search.
        Subsequent searches reuse the cached index.
        """
        if self._tag_index is not None:
            return

        self._tag_index = {}
        for cu_idx, cu in enumerate(self.compilation_units):
            for die in cu.dies:
                if die.tag not in self._tag_index:
                    self._tag_index[die.tag] = []
                self._tag_index[die.tag].append((cu_idx, die))

    def _build_offset_index(self) -> None:
        """Build the offset index mapping DIE offsets to (CU index, DIE) tuples.

        This is a lazy operation - only called once on first offset lookup.
        Subsequent lookups reuse the cached index.
        """
        if self._offset_index is not None:
            return

        self._offset_index = {}
        for cu_idx, cu in enumerate(self.compilation_units):
            for die in cu.dies:
                self._offset_index[die.offset] = (cu_idx, die)

    def _get_cache_key(self) -> Optional[str]:
        """Generate cache key based on ELF file hash and modification time."""
        if not self.elf_file_path or not self.elf_file_path.exists():
            return None

        try:
            # Use first 4KB of file + mtime for cache key
            file_data = self.elf_file_path.read_bytes()[:4096]
            file_hash = sha256(file_data).hexdigest()[:16]
            mtime = int(self.elf_file_path.stat().st_mtime)
            return f"{self.elf_file_path.stem}_{file_hash}_{mtime}"
        except Exception as e:
            logger.warning(f"Failed to generate cache key: {e}")
            return None

    def _load_type_indexes_from_cache(self) -> bool:
        """Load type indexes from disk cache.

        Returns:
            True if loaded successfully, False otherwise
        """
        cache_key = self._get_cache_key()
        if not cache_key:
            return False

        cache_path = self.cache_dir / f"{cache_key}_type_index.pkl"
        if not cache_path.exists():
            return False

        try:
            start_time = time.time()
            with cache_path.open("rb") as f:
                cached_data = pickle.load(f)

            # Validate cache structure
            if not isinstance(cached_data, dict) or "type_names" not in cached_data:
                logger.warning("Invalid cache structure, rebuilding")
                cache_path.unlink(missing_ok=True)
                return False

            # Load the set of type names (lightweight)
            self._all_type_names = cached_data["type_names"]

            # Note: We don't load _type_name_index from cache because it contains
            # DIE references that would be stale. We rebuild it on demand.

            load_time = time.time() - start_time
            logger.info(
                f"✓ Loaded type index from cache: {len(self._all_type_names)} types "
                f"in {load_time:.3f}s"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, rebuilding")
            cache_path.unlink(missing_ok=True)
            return False

    def _save_type_indexes_to_cache(self) -> None:
        """Save type indexes to disk cache."""
        cache_key = self._get_cache_key()
        if not cache_key or not self._all_type_names:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = self.cache_dir / f"{cache_key}_type_index.pkl"

            # Only cache the type name set (lightweight and portable)
            # Don't cache DIE references as they become stale
            cache_data = {"type_names": self._all_type_names}

            with cache_path.open("wb") as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"✓ Saved type index to cache: {cache_path}")

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _build_type_indexes(self) -> None:
        """Build type-specific indexes for fast dependency resolution.

        This index is optimized for class/struct lookups by:
        - Filtering to type DIEs only (class, struct, union)
        - Storing first occurrence per name (deduplication)
        - Building a fast membership set for existence checks
        - Optional disk caching for subsequent runs

        This is a lazy operation - only called once on first type lookup.
        Subsequent lookups reuse the cached indexes.
        """
        if self._type_name_index is not None:
            return

        # Try loading type names from cache
        if self._load_type_indexes_from_cache():
            # Still need to build the index mapping (DIE references can't be cached)
            # But we already have the set of type names for fast existence checks
            pass

        # Build full indexes if not in cache or cache only had partial data
        if self._all_type_names is None:
            start_time = time.time()
            logger.info("Building type indexes...")

            self._type_name_index = {}
            self._all_type_names = set()

            # Type tags we care about for dependency resolution
            type_tags = {
                "DW_TAG_class_type",
                "DW_TAG_structure_type",
                "DW_TAG_union_type",
            }

            type_count = 0
            for cu_idx, cu in enumerate(self.compilation_units):
                for die in cu.dies:
                    if die.tag in type_tags:
                        name = die.get_name()
                        if name:
                            self._all_type_names.add(name)
                            # Store first occurrence only to avoid duplicates
                            if name not in self._type_name_index:
                                self._type_name_index[name] = (cu_idx, die)
                                type_count += 1

            build_time = time.time() - start_time
            logger.info(
                f"✓ Built type indexes: {type_count} unique types "
                f"from {len(self.compilation_units)} CUs in {build_time:.2f}s"
            )

            # Save to cache for next run
            self._save_type_indexes_to_cache()
        else:
            # We loaded type names from cache, now build the DIE index
            start_time = time.time()
            logger.info("Building type DIE index (type names from cache)...")

            self._type_name_index = {}
            type_tags = {
                "DW_TAG_class_type",
                "DW_TAG_structure_type",
                "DW_TAG_union_type",
            }

            for cu_idx, cu in enumerate(self.compilation_units):
                for die in cu.dies:
                    if die.tag in type_tags:
                        name = die.get_name()
                        if name and name not in self._type_name_index:
                            self._type_name_index[name] = (cu_idx, die)

            build_time = time.time() - start_time
            logger.info(f"✓ Built type DIE index in {build_time:.2f}s")

    def find_dies_by_name(self, name: str) -> list[tuple[CompilationUnit, DIE]]:
        """
        Find all DIEs with a specific name across all compilation units.

        Uses lazy-loaded name index for O(1) lookup instead of O(n) scan.

        Args:
            name: The name to search for (value of DW_AT_name)

        Returns:
            List of tuples (CompilationUnit, DIE) matching the name
        """
        self._build_name_index()

        indexed_results = self._name_index.get(name, [])
        return [(self.compilation_units[cu_idx], die) for cu_idx, die in indexed_results]

    def find_dies_by_tag(self, tag: str) -> list[tuple[CompilationUnit, DIE]]:
        """
        Find all DIEs with a specific tag across all compilation units.

        Uses lazy-loaded tag index for O(1) lookup instead of O(n) scan.

        Args:
            tag: The DWARF tag to search for (e.g., 'DW_TAG_class_type')

        Returns:
            List of tuples (CompilationUnit, DIE) matching the tag
        """
        self._build_tag_index()

        indexed_results = self._tag_index.get(tag, [])
        return [(self.compilation_units[cu_idx], die) for cu_idx, die in indexed_results]

    def find_dies_by_predicate(
        self, predicate: Callable[[DIE], bool]
    ) -> list[tuple[CompilationUnit, DIE]]:
        """
        Find all DIEs matching a custom predicate function.

        Args:
            predicate: A function that takes a DIE and returns True if it matches

        Returns:
            List of tuples (CompilationUnit, DIE) matching the predicate
        """
        results: list[tuple[CompilationUnit, DIE]] = []

        for cu in self.compilation_units:
            for die in cu.dies:
                if predicate(die):
                    results.append((cu, die))

        return results

    def find_class_by_name(self, name: str) -> Optional[tuple[CompilationUnit, DIE]]:
        """
        Find a class DIE by name.

        Uses name index for fast lookup, then filters by class tag.
        Early-exits on first match (single result method).

        Args:
            name: The class name to search for

        Returns:
            Tuple (CompilationUnit, DIE) if found, None otherwise
        """
        self._build_name_index()

        indexed_results = self._name_index.get(name, [])
        for cu_idx, die in indexed_results:
            if die.is_class():
                return (self.compilation_units[cu_idx], die)

        return None

    def find_struct_by_name(self, name: str) -> Optional[tuple[CompilationUnit, DIE]]:
        """
        Find a struct DIE by name.

        Uses name index for fast lookup, then filters by struct tag.
        Early-exits on first match (single result method).

        Args:
            name: The struct name to search for

        Returns:
            Tuple (CompilationUnit, DIE) if found, None otherwise
        """
        self._build_name_index()

        indexed_results = self._name_index.get(name, [])
        for cu_idx, die in indexed_results:
            if die.is_struct():
                return (self.compilation_units[cu_idx], die)

        return None

    def get_die_by_offset(
        self, offset: int, cu: Optional[CompilationUnit] = None
    ) -> Optional[DIE]:
        """
        Get a DIE by its offset.

        Uses offset index for O(1) lookup when searching all CUs.
        Falls back to linear search when specific CU provided.

        Args:
            offset: The DIE offset to search for
            cu: Optional specific compilation unit to search in

        Returns:
            The DIE if found, None otherwise
        """
        if cu is not None:
            # Specific CU search - linear scan within that CU only
            for die in cu.dies:
                if die.offset == offset:
                    return die
            return None

        # Global search - use index
        self._build_offset_index()
        result = self._offset_index.get(offset)
        return result[1] if result else None

    def find_type_by_name(self, name: str) -> Optional[tuple[CompilationUnit, DIE]]:
        """
        Find a type (class/struct/union) DIE by name using optimized type index.

        This method is faster than find_class_by_name() or find_struct_by_name()
        because it uses a dedicated type-only index with deduplication.

        Args:
            name: The type name to search for

        Returns:
            Tuple (CompilationUnit, DIE) if found, None otherwise
        """
        self._build_type_indexes()

        result = self._type_name_index.get(name)
        return (self.compilation_units[result[0]], result[1]) if result else None

    def type_exists(self, name: str) -> bool:
        """
        Fast O(1) check if a type exists without full DIE lookup.

        This is significantly faster than find_type_by_name() when you only
        need to check existence, as it uses a set instead of returning DIE objects.

        Args:
            name: The type name to check

        Returns:
            True if type exists, False otherwise
        """
        self._build_type_indexes()
        return name in self._all_type_names

    def get_all_classes(self) -> list[tuple[CompilationUnit, DIE]]:
        """
        Get all class type DIEs.

        Returns:
            List of tuples (CompilationUnit, DIE) for all classes
        """
        return self.find_dies_by_tag("DW_TAG_class_type")

    def get_all_structs(self) -> list[tuple[CompilationUnit, DIE]]:
        """
        Get all struct type DIEs.

        Returns:
            List of tuples (CompilationUnit, DIE) for all structs
        """
        return self.find_dies_by_tag("DW_TAG_structure_type")

    def get_members(self, class_die: DIE) -> list[DIE]:
        """
        Get all member variables of a class/struct.

        Args:
            class_die: The class or struct DIE

        Returns:
            List of member DIEs
        """
        return [child for child in class_die.children if child.is_member()]

    def get_methods(self, class_die: DIE) -> list[DIE]:
        """
        Get all methods (subprograms) of a class.

        Args:
            class_die: The class DIE

        Returns:
            List of method DIEs
        """
        return [child for child in class_die.children if child.is_subprogram()]

    def print_die_summary(self, die: DIE, indent: int = 0) -> None:
        """
        Print a summary of a DIE with indentation.

        Args:
            die: The DIE to print
            indent: The indentation level
        """
        indent_str = "  " * indent
        name = die.get_name()
        print(f"{indent_str}{die.tag}", end="")
        if name:
            print(f": {name}", end="")

        byte_size = die.get_byte_size()
        if byte_size is not None:
            print(f" (size: {byte_size} bytes)", end="")

        print()

        # Print key attributes
        for attr_name in ["DW_AT_decl_file", "DW_AT_decl_line", "DW_AT_accessibility"]:
            if attr := die.get_attribute(attr_name):
                print(f"{indent_str}  {attr_name}: {attr.value}")

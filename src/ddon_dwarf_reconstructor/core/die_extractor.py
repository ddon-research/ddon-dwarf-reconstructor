"""Utility for extracting and searching DIEs from DWARF information."""

from typing import Callable, Optional

from .models import CompilationUnit, DIE


class DIEExtractor:
    """Extracts and searches Debug Information Entries from compilation units.

    Performance optimizations based on Ghidra DWARF parser insights:
    - Lazy index building: Indexes built on-demand, cached for reuse
    - Symbol name index: Maps symbol names to (CU index, DIE) for fast lookup
    - Tag index: Maps DWARF tags to DIEs for type searches
    - Early-exit searches: Stop immediately when target found (for single-result methods)
    """

    def __init__(self, compilation_units: list[CompilationUnit]) -> None:
        """
        Initialize the DIE extractor.

        Args:
            compilation_units: List of parsed compilation units
        """
        self.compilation_units = compilation_units

        # Lazy-loaded indexes (built on first use, cached thereafter)
        self._name_index: Optional[dict[str, list[tuple[int, DIE]]]] = None
        self._tag_index: Optional[dict[str, list[tuple[int, DIE]]]] = None
        self._offset_index: Optional[dict[int, tuple[int, DIE]]] = None

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

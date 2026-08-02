"""DWARF lookup operations for the application generator."""

from __future__ import annotations

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import calculate_packing_info
from .dwarf_generator_context import DwarfGeneratorContext


class GeneratorLookupService:
    def find_class(
        self: DwarfGeneratorContext, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find a class/type DIE by name.

        Delegates to ClassParser for the search.

        Args:
            class_name: Name of the class to find

        Returns:
            Tuple of (compilation unit, DIE) if found, None otherwise
        """
        parser = self.class_parser
        assert parser is not None
        return parser.find_class(class_name)

    def is_namespace(self: DwarfGeneratorContext, die: DwarfEntry) -> bool:
        """Check if a DIE represents a namespace.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a namespace, False otherwise
        """
        return die.tag == "DW_TAG_namespace"

    def parse_class_info(
        self: DwarfGeneratorContext, cu: DwarfCompilationUnit, class_die: DwarfEntry
    ) -> ClassInfo:
        """Parse class information from a DIE.

        Delegates to ClassParser and adds packing analysis.

        Args:
            cu: Compilation unit containing the class
            class_die: DIE representing the class

        Returns:
            ClassInfo object with complete information including packing
        """
        parser = self.class_parser
        assert parser is not None
        class_info = parser.parse_class_info(cu, class_die)

        # Add packing information
        class_info.packing_info = calculate_packing_info(class_info)

        return class_info

    def build_inheritance_hierarchy(self: DwarfGeneratorContext, class_name: str) -> list[str]:
        """Build inheritance chain for a class.

        Args:
            class_name: Name of the class

        Returns:
            List of base class names from root to derived
        """
        assert self.hierarchy_builder is not None
        return self.hierarchy_builder.build_hierarchy_chain(class_name)

"""DWARF lookup operations for the application generator."""

from __future__ import annotations

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import calculate_packing_info
from ..generation.runtime import GenerationRuntime


class GeneratorLookupService:
    @staticmethod
    def find_class(
        context: GenerationRuntime, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find a class/type DIE by name.

        Delegates to ClassParser for the search.

        Args:
            class_name: Name of the class to find

        Returns:
            Tuple of (compilation unit, DIE) if found, None otherwise
        """
        return context.class_parser.find_class(class_name)

    @staticmethod
    def is_namespace(_context: GenerationRuntime, die: DwarfEntry) -> bool:
        """Check if a DIE represents a namespace.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a namespace, False otherwise
        """
        return die.tag == "DW_TAG_namespace"

    @staticmethod
    def parse_class_info(
        context: GenerationRuntime, cu: DwarfCompilationUnit, class_die: DwarfEntry
    ) -> ClassInfo:
        """Parse class information from a DIE.

        Delegates to ClassParser and adds packing analysis.

        Args:
            cu: Compilation unit containing the class
            class_die: DIE representing the class

        Returns:
            ClassInfo object with complete information including packing
        """
        class_info = context.class_parser.parse_class_info(cu, class_die)

        # Add packing information
        class_info.packing_info = calculate_packing_info(class_info)

        return class_info

    @staticmethod
    def build_inheritance_hierarchy(context: GenerationRuntime, class_name: str) -> list[str]:
        """Build inheritance chain for a class.

        Args:
            class_name: Name of the class

        Returns:
            List of base class names from root to derived
        """
        return context.hierarchy_builder.build_hierarchy_chain(class_name)

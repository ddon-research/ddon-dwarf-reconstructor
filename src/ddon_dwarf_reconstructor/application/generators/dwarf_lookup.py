"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import calculate_packing_info
from .dwarf_generator_context import DwarfGeneratorContext


class GeneratorLookupMixin:
    def find_class(self: DwarfGeneratorContext, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find a class/type DIE by name.

        Delegates to ClassParser for the search.

        Args:
            class_name: Name of the class to find

        Returns:
            Tuple of (CompileUnit, DIE) if found, None otherwise
        """
        parser = self.class_parser
        assert parser is not None
        return parser.find_class(class_name)

    def is_namespace(self: DwarfGeneratorContext, die: DIE) -> bool:
        """Check if a DIE represents a namespace.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a namespace, False otherwise
        """
        return die.tag == "DW_TAG_namespace"

    def parse_class_info(self: DwarfGeneratorContext, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Parse class information from DIE.

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

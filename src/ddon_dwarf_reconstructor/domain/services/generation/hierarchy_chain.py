"""Inheritance-chain operations for hierarchy building."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger, log_timing

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .hierarchy_builder_context import HierarchyBuilderContext


class HierarchyChainMixin:
    @log_timing
    def build_hierarchy_chain(self: HierarchyBuilderContext, class_name: str) -> list[str]:
        """Build inheritance chain returning only class names.

        Simpler version that just returns the list of base class names
        without parsing full ClassInfo.

        Args:
            class_name: Name of the target class

        Returns:
            List of base class names from root to derived (excluding target class)
        """
        hierarchy = []
        current_class = class_name
        visited = set()

        while current_class and current_class not in visited:
            visited.add(current_class)

            result = self.class_parser.find_class(current_class, exhaustive_override=False)
            if not result:
                break

            _, class_die = result

            # Find base class
            next_class = self._find_base_class(class_die)
            if next_class and next_class != "unknown_type":
                hierarchy.append(next_class)
                current_class = next_class
            else:
                break

        return list(reversed(hierarchy))  # Base to derived order

    def _find_base_class(self: HierarchyBuilderContext, class_die: DwarfEntry) -> str | None:
        """Find the direct base class from a class DIE.

        Args:
            class_die: DIE representing a class

        Returns:
            Base class name if found, None otherwise
        """
        for child in class_die.iter_children():
            if child.tag == "DW_TAG_inheritance":
                base_type = self.class_parser.type_resolver.resolve_type_name(child)
                if base_type != "unknown_type":
                    return base_type
        return None

    def _get_base_class_chain(self: HierarchyBuilderContext, class_name: str) -> list[str]:
        """Get complete base class chain for a class.

        This method walks the inheritance hierarchy from the given class
        to its root base class, collecting all intermediate base classes.
        Used to ensure complete inheritance chains are included when
        resolving dependencies.

        Args:
            class_name: Name of the class to get base classes for

        Returns:
            List of base class names from immediate parent to root (MtObject, etc.)
            Empty list if class has no base classes or couldn't be found
        """
        base_classes: list[str] = []
        current_class = class_name
        visited = set()

        while current_class and current_class not in visited:
            visited.add(current_class)

            result = self.class_parser.find_class(current_class, exhaustive_override=False)
            if not result:
                break

            _cu, class_die = result

            # Find base class
            base_name = self._find_base_class(class_die)
            if base_name and base_name != "unknown_type":
                base_classes.append(base_name)
                current_class = base_name
            else:
                break

        return base_classes

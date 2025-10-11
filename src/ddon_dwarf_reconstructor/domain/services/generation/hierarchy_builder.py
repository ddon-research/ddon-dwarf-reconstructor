#!/usr/bin/env python3

"""Inheritance hierarchy building and full hierarchy generation.

This module handles building complete inheritance chains and collecting
all classes in an inheritance hierarchy for full hierarchy header generation.
"""

from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger, log_timing
from ...models.dwarf import ClassInfo
from ..lazy_dwarf_index_service import LazyDwarfIndexService
from ..parsing.class_parser import ClassParser
from .dependency_extractor import DependencyExtractor

logger = get_logger(__name__)


class HierarchyBuilder:
    """Builds complete inheritance hierarchies for classes.

    This class handles:
    - Building inheritance chains from derived to base
    - Collecting all ClassInfo objects in a hierarchy
    - Ordering classes from base to derived for proper generation
    """

    def __init__(self, class_parser: ClassParser, dwarf_index: LazyDwarfIndexService):
        """Initialize hierarchy builder with class parser and DWARF index.

        Args:
            class_parser: ClassParser instance for finding and parsing classes
            dwarf_index: DWARF index for offset-based dependency resolution (required)
        """
        self.class_parser = class_parser
        self.dwarf_index = dwarf_index
        self.dependency_extractor = DependencyExtractor(dwarf_index)

    @log_timing
    def build_full_hierarchy(
        self,
        class_name: str,
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build complete inheritance hierarchy for a class.

        Traverses from derived class back to root base class, parsing all
        classes in the chain.

        Args:
            class_name: Name of the target class

        Returns:
            Tuple of (class_infos_dict, hierarchy_order_list)
            - class_infos_dict: Mapping of class name -> ClassInfo
            - hierarchy_order_list: List of class names from base to derived
        """
        logger.info(f"Building full inheritance hierarchy for: {class_name}")

        all_class_infos: dict[str, ClassInfo] = {}
        hierarchy_order: list[str] = []

        current_class = class_name
        visited = set()

        while current_class and current_class not in visited:
            visited.add(current_class)
            logger.debug(f"Processing class in hierarchy: {current_class}")

            result = self.class_parser.find_class(current_class)
            if not result:
                logger.warning(f"Could not find class: {current_class}")
                break

            cu, class_die = result
            class_info = self.class_parser.parse_class_info(cu, class_die)
            all_class_infos[current_class] = class_info
            hierarchy_order.insert(0, current_class)  # Insert at beginning for base->derived order

            # Find base class
            next_class = self._find_base_class(class_die)
            if next_class and next_class != "unknown_type":
                logger.debug(f"Found base class: {next_class}")
                current_class = next_class
            else:
                logger.debug(f"No base class found for: {current_class}")
                break

        logger.info(
            f"Hierarchy complete: {len(all_class_infos)} classes, "
            f"order: {' -> '.join(hierarchy_order)}",
        )

        return all_class_infos, hierarchy_order

    @log_timing
    def build_full_hierarchy_with_dependencies(
        self,
        class_name: str,
        max_depth: int = 10,
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build complete hierarchy with full recursive dependency resolution.

        This traverses not just the inheritance chain, but recursively resolves
        all types referenced in members, methods, nested structs, and unions.

        Uses offset-based dependency extraction if DependencyExtractor is available,
        otherwise falls back to legacy string-based extraction.

        Args:
            class_name: Name of the target class
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            Tuple of (class_infos_dict, hierarchy_order_list)
            - class_infos_dict: All resolved classes including dependencies
            - hierarchy_order_list: Main hierarchy from base to derived
        """
        logger.info(f"Building full hierarchy with dependencies for: {class_name}")

        # First, build the main inheritance hierarchy
        hierarchy_classes, hierarchy_order = self.build_full_hierarchy(class_name)

        # Track all classes (hierarchy + dependencies)
        all_classes: dict[str, ClassInfo] = dict(hierarchy_classes)

        # Process dependencies using offset-based extraction
        self._process_dependencies_offset_based(hierarchy_classes, all_classes, max_depth)

        logger.info(
            f"Resolved {len(all_classes)} total classes "
            f"({len(hierarchy_classes)} in main hierarchy, "
            f"{len(all_classes) - len(hierarchy_classes)} dependencies)",
        )

        return all_classes, hierarchy_order

    def _process_dependencies_offset_based(
        self,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        max_depth: int,
    ) -> None:
        """Process dependencies using offset-based extraction.

        Args:
            hierarchy_classes: Initial hierarchy classes
            all_classes: Dictionary to populate with all resolved classes
            max_depth: Maximum recursion depth
        """
        if not self.dependency_extractor or not self.dwarf_index:
            return

        # Track processing
        to_process_offsets: set[int] = set()
        processed_offsets: set[int] = set()
        depth_map: dict[int, int] = {}

        # Extract dependencies from hierarchy classes
        for class_info in hierarchy_classes.values():
            offsets = self.dependency_extractor.extract_dependencies(class_info)
            for offset in offsets:
                if offset not in processed_offsets:
                    to_process_offsets.add(offset)
                    depth_map[offset] = 0

        # Recursively process dependencies
        while to_process_offsets:
            current_offset = to_process_offsets.pop()
            if current_offset in processed_offsets:
                continue

            processed_offsets.add(current_offset)
            current_depth = depth_map.get(current_offset, 0)

            if current_depth >= max_depth:
                logger.debug(f"Reached max depth for offset 0x{current_offset:x}")
                continue

            # Filter to only resolvable types
            if not self.dependency_extractor.filter_resolvable_types({current_offset}):
                continue

            # Get type name and resolve
            type_name = self.dependency_extractor.get_type_name(current_offset)
            if not type_name:
                logger.debug(f"No name for offset 0x{current_offset:x}")
                continue

            # Filter out internal DWARF type names
            internal_types = {
                "class_type",
                "structure_type",
                "union_type",
                "unknown_type",
                "subroutine_type",
            }
            if type_name in internal_types:
                logger.debug(f"Skipping internal type: {type_name}")
                continue

            if type_name in all_classes:
                # Already resolved
                class_info = all_classes[type_name]
            else:
                # Try to resolve
                class_info = self._try_resolve_type_by_offset(current_offset, type_name)
                if not class_info:
                    continue

                all_classes[type_name] = class_info
                logger.debug(f"Resolved dependency: {type_name} (depth {current_depth})")

            # Extract and queue new dependencies
            new_offsets = self.dependency_extractor.extract_dependencies(class_info)
            resolvable = self.dependency_extractor.filter_resolvable_types(new_offsets)

            for dep_offset in resolvable:
                if dep_offset not in processed_offsets:
                    to_process_offsets.add(dep_offset)
                    depth_map[dep_offset] = current_depth + 1

    def _try_resolve_type_by_offset(
        self, offset: int, type_name: str
    ) -> ClassInfo | None:
        """Try to resolve and parse a type by its DIE offset.

        Args:
            offset: DIE offset of the type
            type_name: Name of type (for logging)

        Returns:
            ClassInfo if successfully parsed, None otherwise
        """
        # Use find_class which returns (CU, DIE) tuple
        try:
            result = self.class_parser.find_class(type_name)
            if not result:
                logger.debug(f"Could not find class: {type_name}")
                return None

            cu, die = result

            # Skip enums and typedefs - they don't need full resolution
            if die.tag in ("DW_TAG_enumeration_type", "DW_TAG_typedef"):
                logger.debug(
                    f"Skipping {die.tag.replace('DW_TAG_', '')} type: {type_name}"
                )
                return None

            # Parse the class
            return self.class_parser.parse_class_info(cu, die)

        except Exception as e:
            logger.debug(f"Failed to resolve type {type_name} at 0x{offset:x}: {e}")
            return None

    @log_timing
    def build_hierarchy_chain(self, class_name: str) -> list[str]:
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

            result = self.class_parser.find_class(current_class)
            if not result:
                break

            cu, class_die = result

            # Find base class
            next_class = self._find_base_class(class_die)
            if next_class and next_class != "unknown_type":
                hierarchy.append(next_class)
                current_class = next_class
            else:
                break

        return list(reversed(hierarchy))  # Base to derived order

    def _find_base_class(self, class_die: DIE) -> str | None:
        """Find direct base class from a class DIE.

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

#!/usr/bin/env python3

"""Inheritance hierarchy building and full hierarchy generation.

This module handles building complete inheritance chains and collecting
all classes in an inheritance hierarchy for full hierarchy header generation.
"""

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger, log_timing
from ...models.dwarf import ClassInfo
from ...ports.class_parser import ClassParserPort
from ...ports.dwarf_lookup import DwarfLookupPort
from .dependency_extractor import DependencyExtractor
from .hierarchy_builder_context import HierarchyBuilderContext
from .hierarchy_chain import HierarchyChainMixin
from .hierarchy_dependencies import HierarchyDependencyMixin, HierarchyDependencyWorkMixin
from .hierarchy_dependency_lookup import HierarchyDependencyLookupMixin

logger = get_logger(__name__)


class HierarchyBuilder(
    HierarchyDependencyMixin,
    HierarchyDependencyWorkMixin,
    HierarchyDependencyLookupMixin,
    HierarchyChainMixin,
    HierarchyBuilderContext,
):
    """Builds complete inheritance hierarchies for classes.

    This class handles:
    - Building inheritance chains from derived to base
    - Collecting all ClassInfo objects in a hierarchy
    - Ordering classes from base to derived for proper generation
    """

    def __init__(self, class_parser: ClassParserPort, dwarf_index: DwarfLookupPort):
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
        self: HierarchyBuilderContext,
        class_name: str,
        root_die_offset: int | None = None,
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

        is_root_lookup = True
        pending_base_offset: int | None = None
        while current_class and current_class not in visited:
            visited.add(current_class)
            logger.debug(f"Processing class in hierarchy: {current_class}")

            result = self._lookup_hierarchy_class(
                current_class,
                class_name,
                is_root_lookup,
                root_die_offset,
                pending_base_offset,
            )
            if not result:
                logger.warning(f"Could not find class: {current_class}")
                break

            cu, class_die = result
            class_info = self.class_parser.parse_class_info(cu, class_die)
            all_class_infos[current_class] = class_info
            hierarchy_order.insert(0, current_class)  # Insert at beginning for base->derived order

            next_class, next_base_offset = self._next_hierarchy_base(class_info, class_die)
            if next_class and next_class != "unknown_type":
                logger.debug(f"Found base class: {next_class}")
                current_class = next_class
                pending_base_offset = next_base_offset
                is_root_lookup = False
            else:
                logger.debug(f"No base class found for: {current_class}")
                break

        logger.info(
            f"Hierarchy complete: {len(all_class_infos)} classes, "
            f"order: {' -> '.join(hierarchy_order)}",
        )

        return all_class_infos, hierarchy_order

    def _lookup_hierarchy_class(
        self: HierarchyBuilderContext,
        current_class: str,
        root_class: str,
        is_root_lookup: bool,
        root_die_offset: int | None,
        pending_base_offset: int | None,
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        if is_root_lookup and root_die_offset is not None:
            result = self.class_parser._find_die_and_cu_by_offset(root_die_offset)
            if result is None:
                raise ValueError(
                    f"Approved root DIE 0x{root_die_offset:x} is unavailable for {root_class}"
                )
            return result
        if pending_base_offset is not None:
            result = self.class_parser._find_die_and_cu_by_offset(pending_base_offset)
            if result is not None:
                return result
        return self.class_parser.find_class(
            current_class,
            exhaustive_override=None if is_root_lookup else False,
        )

    def _next_hierarchy_base(
        self: HierarchyBuilderContext, class_info: ClassInfo, class_die: DwarfEntry
    ) -> tuple[str | None, int | None]:
        next_class = class_info.base_classes[0] if class_info.base_classes else None
        if next_class is None:
            next_class = self._find_base_class(class_die)
        next_base_offset = (
            class_info.base_class_offsets[0] if class_info.base_class_offsets else None
        )
        return next_class, next_base_offset

    @log_timing
    def build_full_hierarchy_with_dependencies(
        self: HierarchyBuilderContext,
        class_name: str,
        max_depth: int = 10,
        root_die_offset: int | None = None,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build complete hierarchy with full recursive dependency resolution.

        This traverses not just the inheritance chain, but recursively resolves
        all types referenced in members, methods, nested structs, and unions.

        Uses the dependency extractor and DIE offsets to resolve referenced types.

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
        hierarchy_classes, hierarchy_order = self.build_full_hierarchy(
            class_name, root_die_offset=root_die_offset
        )

        # Track all classes (hierarchy + dependencies)
        all_classes: dict[str, ClassInfo] = dict(hierarchy_classes)

        # Process dependencies using offset-based extraction
        self._process_dependencies_offset_based(
            hierarchy_classes,
            all_classes,
            max_depth,
            include_method_signatures=include_method_signatures,
        )

        logger.info(
            f"Resolved {len(all_classes)} total classes "
            f"({len(hierarchy_classes)} in main hierarchy, "
            f"{len(all_classes) - len(hierarchy_classes)} dependencies)",
        )

        return all_classes, hierarchy_order

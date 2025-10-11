#!/usr/bin/env python3

"""Inheritance hierarchy building and full hierarchy generation.

This module handles building complete inheritance chains and collecting
all classes in an inheritance hierarchy for full hierarchy header generation.
"""

from elftools.dwarf.die import DIE

from ...models.dwarf import ClassInfo
from ....infrastructure.logging import get_logger, log_timing
from ..parsing.class_parser import ClassParser

logger = get_logger(__name__)


class HierarchyBuilder:
    """Builds complete inheritance hierarchies for classes.

    This class handles:
    - Building inheritance chains from derived to base
    - Collecting all ClassInfo objects in a hierarchy
    - Ordering classes from base to derived for proper generation
    """

    def __init__(self, class_parser: ClassParser):
        """Initialize hierarchy builder with class parser.

        Args:
            class_parser: ClassParser instance for finding and parsing classes
        """
        self.class_parser = class_parser

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

    def collect_hierarchy_with_dependencies(
        self,
        class_name: str,
        include_basic_types: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str], dict[str, ClassInfo]]:
        """Build hierarchy and collect dependent types.

        In addition to the inheritance hierarchy, this method also resolves
        and includes simple dependent types (like MtFloat3, MtString) that
        are used by hierarchy classes.

        Args:
            class_name: Name of the target class
            include_basic_types: If True, resolve and include basic Mt types

        Returns:
            Tuple of (hierarchy_classes, hierarchy_order, additional_types)
            - hierarchy_classes: Main inheritance hierarchy classes
            - hierarchy_order: Class names in base->derived order
            - additional_types: Additional resolved types to include
        """
        # Build main hierarchy
        hierarchy_classes, hierarchy_order = self.build_full_hierarchy(class_name)

        additional_types = {}

        if include_basic_types:
            # Collect types used by hierarchy classes
            used_types = set()
            for class_info in hierarchy_classes.values():
                for member in class_info.members:
                    clean_type = self._extract_type_name(member.type_name)
                    if clean_type and not clean_type.endswith("*"):
                        used_types.add(clean_type)

            # Try to resolve basic Mt types
            for type_name in used_types:
                # Looks like a basic Mt type and not already in hierarchy
                if (
                    type_name.startswith("Mt")
                    and len(type_name) < 20
                    and type_name not in hierarchy_classes
                ):
                    type_info = self._try_resolve_type(type_name)
                    if type_info and self._is_simple_type(type_info):
                        additional_types[type_name] = type_info
                        logger.debug(f"Resolved additional type: {type_name}")

        logger.info(
            f"Collected {len(hierarchy_classes)} hierarchy classes and "
            f"{len(additional_types)} additional types",
        )

        return hierarchy_classes, hierarchy_order, additional_types

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

    def _extract_type_name(self, full_type: str) -> str | None:
        """Extract clean type name from qualified type.

        Args:
            full_type: Full type string with qualifiers

        Returns:
            Clean type name without const/pointer/reference
        """
        clean = full_type.strip()

        # Remove const
        if clean.startswith("const "):
            clean = clean[6:].strip()

        # Remove pointer/reference
        clean = clean.rstrip("*&").strip()

        # Skip arrays
        if "[" in clean:
            return None

        # Skip primitives
        primitives = {
            "void",
            "bool",
            "char",
            "int",
            "float",
            "double",
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
        }
        if clean in primitives:
            return None

        return clean

    def _try_resolve_type(self, type_name: str) -> ClassInfo | None:
        """Try to resolve and parse a type.

        Args:
            type_name: Name of type to resolve

        Returns:
            ClassInfo if successfully parsed, None otherwise
        """
        try:
            result = self.class_parser.find_class(type_name)
            if result:
                cu, die = result
                return self.class_parser.parse_class_info(cu, die)
        except Exception as e:
            logger.debug(f"Failed to resolve type {type_name}: {e}")

        return None

    def _is_simple_type(self, class_info: ClassInfo) -> bool:
        """Check if a type is simple enough to include in hierarchy header.

        Simple types are small structures with few members that won't
        significantly bloat the header.

        Args:
            class_info: ClassInfo to check

        Returns:
            True if type is simple, False otherwise
        """
        # Small size and few members
        return class_info.byte_size <= 64 and len(class_info.members) <= 10

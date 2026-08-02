"""Header generation operations for the application generator."""

from __future__ import annotations

from time import time

from ...core.observability import get_logger, log_timing
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import SpecialHeaderRenderer, calculate_packing_info
from .dwarf_generator_context import DwarfGeneratorContext

logger = get_logger(__name__)


class HeaderGenerationService:
    @log_timing
    def generate_header(
        self: DwarfGeneratorContext, class_name: str, include_metadata: bool = True
    ) -> str:
        """Generate C++ header for a single class or namespace.

        Args:
            class_name: Name of the class/namespace to generate header for
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        logger.info(f"Generating header for: {class_name}")

        # Find class with timing
        find_start = time()
        result = self.workflow.find_class(class_name)
        find_elapsed = time() - find_start
        logger.debug(f"Class search completed in {find_elapsed:.3f}s")

        if not result:
            logger.warning(f"Class {class_name} not found")
            return SpecialHeaderRenderer.render_not_found(class_name)

        cu, class_die = result

        # Check if this is a namespace
        if self.workflow.is_namespace(class_die):
            logger.info(f"{class_name} is a namespace, generating namespace header")
            return SpecialHeaderRenderer.render_namespace(class_name, cu, class_die)

        # Build a complete closure so standalone output defines bases and by-value types.
        self.workflow.expand_typedef_search(full_hierarchy=True)
        class_infos, hierarchy_order = self.workflow.build_hierarchy_with_timing(
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )
        if not self.workflow.validate_hierarchy(class_infos, class_name):
            return SpecialHeaderRenderer.render_not_found(class_name)

        typedefs = self.workflow.collect_typedefs_and_packing(class_infos)

        header_start = time()
        assert self.header_generator is not None
        header = self.header_generator.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            class_name,
            typedefs=typedefs,
            include_metadata=include_metadata,
            guard_suffix="_H",
        )
        header_elapsed = time() - header_start
        logger.debug(f"Header generation completed in {header_elapsed:.3f}s")

        logger.info(f"Header generated successfully for {class_name}")
        return header

    def _expand_typedef_search(self: DwarfGeneratorContext, full_hierarchy: bool = True) -> None:
        """Expand typedef search for hierarchy generation.

        Args:
            full_hierarchy: Enable full hierarchy mode
        """
        typedef_expand_start = time()
        resolver = self.type_resolver
        assert resolver is not None
        resolver.expand_primitive_search(full_hierarchy=full_hierarchy)
        typedef_expand_elapsed = time() - typedef_expand_start
        logger.debug(f"Typedef search expansion completed in {typedef_expand_elapsed:.3f}s")

    def _build_hierarchy_with_timing(
        self: DwarfGeneratorContext,
        class_name: str,
        max_depth: int = 10,
        *,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build full hierarchy with dependencies and timing.

        Args:
            class_name: Target class name
            max_depth: Maximum inheritance depth
            include_method_signatures: Include method return and parameter types
                in the dependency closure

        Returns:
            Tuple of (class_infos dict, hierarchy_order list)
        """
        hierarchy_start = time()
        assert self.hierarchy_builder is not None
        class_infos, hierarchy_order = (
            self.hierarchy_builder.build_full_hierarchy_with_dependencies(
                class_name,
                max_depth=max_depth,
                include_method_signatures=include_method_signatures,
            )
        )
        hierarchy_elapsed = time() - hierarchy_start
        logger.debug(f"Hierarchy building completed in {hierarchy_elapsed:.3f}s")
        return class_infos, hierarchy_order

    def _validate_hierarchy(
        self: DwarfGeneratorContext, class_infos: dict[str, ClassInfo], class_name: str
    ) -> bool:
        """Validate hierarchy is not empty.

        Args:
            class_infos: Dictionary of class information
            class_name: Target class name

        Returns:
            True if valid, False if empty
        """
        if not class_infos:
            logger.warning(f"No classes found in hierarchy for {class_name}")
            return False
        return True

    def _collect_typedefs_and_packing(
        self: DwarfGeneratorContext, class_infos: dict[str, ClassInfo]
    ) -> dict[str, str]:
        """Add packing info and collect all typedefs from classes.

        Args:
            class_infos: Dictionary of class information

        Returns:
            Dictionary of collected typedefs
        """
        packing_start = time()
        all_typedefs: dict[str, str] = {}
        resolver = self.type_resolver
        assert resolver is not None

        for _cls_name, class_info in class_infos.items():
            if class_info.packing_info is None:
                class_info.packing_info = calculate_packing_info(class_info)

            # Collect typedefs for this class
            class_typedefs = resolver.collect_used_typedefs(
                class_info.members,
                class_info.methods,
                class_info.unions,
                class_info.nested_structs,
            )
            all_typedefs.update(class_typedefs)

        packing_elapsed = time() - packing_start
        logger.debug(f"Packing analysis and typedef collection completed in {packing_elapsed:.3f}s")

        return all_typedefs

    @log_timing
    def generate_complete_hierarchy_header(
        self: DwarfGeneratorContext,
        class_name: str,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header with complete inheritance hierarchy.

        This method generates headers for the entire inheritance chain,
        from base class to derived class, with proper ordering.

        Args:
            class_name: Name of the target class
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file with full hierarchy
        """
        logger.info(f"Generating complete hierarchy header for: {class_name}")

        # Step 1: Expand typedef search
        self.workflow.expand_typedef_search(full_hierarchy=True)

        # Step 2: Build full hierarchy with dependencies
        class_infos, hierarchy_order = self.workflow.build_hierarchy_with_timing(
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )

        # Step 3: Validate hierarchy
        if not self.workflow.validate_hierarchy(class_infos, class_name):
            return SpecialHeaderRenderer.render_not_found(class_name)

        # Step 4: Add packing info and collect typedefs
        all_typedefs = self.workflow.collect_typedefs_and_packing(class_infos)

        logger.info(
            f"Hierarchy complete: {len(class_infos)} classes in order: "
            f"{' -> '.join(hierarchy_order)}, collected {len(all_typedefs)} typedefs",
        )

        # Generate hierarchy header with timing
        header_gen_start = time()
        assert self.header_generator is not None
        header = self.header_generator.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            class_name,
            typedefs=all_typedefs,
            include_metadata=include_metadata,
            guard_suffix="_H",
        )
        header_gen_elapsed = time() - header_gen_start
        logger.debug(f"Hierarchy header generation completed in {header_gen_elapsed:.3f}s")

        logger.info(f"Hierarchy header generated successfully for {class_name}")
        return header

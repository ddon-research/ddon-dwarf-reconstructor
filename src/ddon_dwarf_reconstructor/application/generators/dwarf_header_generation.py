"""Header generation operations for the application generator."""

from __future__ import annotations

import logging
from time import perf_counter

from ...core.observability import get_logger, log_event, log_timing
from ...domain.services.generation import SpecialHeaderRenderer
from ..generation.runtime import GenerationRuntime
from .dwarf_header_support import HeaderGenerationSupportMixin
from .dwarf_lookup import GeneratorLookupService

logger = get_logger(__name__)


class HeaderGenerationService(HeaderGenerationSupportMixin):
    @staticmethod
    @log_timing
    def generate_header(
        context: GenerationRuntime, class_name: str, include_metadata: bool = True
    ) -> str:
        """Generate C++ header for a single class or namespace.

        Args:
            class_name: Name of the class/namespace to generate header for
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        log_event(
            logger,
            logging.INFO,
            "header_generation_started",
            symbol=class_name,
            include_metadata=include_metadata,
            mode="single-header",
        )

        result = HeaderGenerationService._find_class_with_timing(context, class_name)

        if not result:
            log_event(logger, logging.WARNING, "class_not_found", symbol=class_name)
            return SpecialHeaderRenderer.render_not_found(class_name)

        cu, class_die = result

        # Check if this is a namespace
        if GeneratorLookupService.is_namespace(context, class_die):
            log_event(logger, logging.INFO, "namespace_header_generation", symbol=class_name)
            return SpecialHeaderRenderer.render_namespace(class_name, cu, class_die)

        # Build a complete closure so standalone output defines bases and by-value types.
        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)
        class_infos, hierarchy_order = HeaderGenerationService._build_hierarchy_with_timing(
            context,
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )
        if not HeaderGenerationService._validate_hierarchy(context, class_infos, class_name):
            return SpecialHeaderRenderer.render_not_found(class_name)

        typedefs = HeaderGenerationService._collect_typedefs_and_packing(context, class_infos)

        header_start = perf_counter()
        header = context.header_renderer.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            class_name,
            typedefs=typedefs,
            include_metadata=include_metadata,
            guard_suffix="_H",
        )
        log_event(
            logger,
            logging.DEBUG,
            "header_render_completed",
            symbol=class_name,
            duration_ms=round((perf_counter() - header_start) * 1000, 3),
            class_count=len(class_infos),
            typedef_count=len(typedefs),
            byte_count=len(header.encode("utf-8")),
        )
        log_event(logger, logging.INFO, "header_generation_completed", symbol=class_name)
        return header

    @staticmethod
    @log_timing
    def generate_complete_hierarchy_header(
        context: GenerationRuntime,
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
        log_event(
            logger,
            logging.INFO,
            "header_generation_started",
            symbol=class_name,
            include_metadata=include_metadata,
            mode="full-hierarchy-single-file",
        )

        # Step 1: Expand typedef search
        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)

        # Step 2: Build full hierarchy with dependencies
        class_infos, hierarchy_order = HeaderGenerationService._build_hierarchy_with_timing(
            context,
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )

        # Step 3: Validate hierarchy
        if not HeaderGenerationService._validate_hierarchy(context, class_infos, class_name):
            return SpecialHeaderRenderer.render_not_found(class_name)

        # Step 4: Add packing info and collect typedefs
        all_typedefs = HeaderGenerationService._collect_typedefs_and_packing(context, class_infos)

        log_event(
            logger,
            logging.DEBUG,
            "hierarchy_closure_ready",
            symbol=class_name,
            class_count=len(class_infos),
            hierarchy_order=hierarchy_order,
            typedef_count=len(all_typedefs),
        )

        # Generate hierarchy header with timing
        header_gen_start = perf_counter()
        header = context.header_renderer.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            class_name,
            typedefs=all_typedefs,
            include_metadata=include_metadata,
            guard_suffix="_H",
        )
        log_event(
            logger,
            logging.DEBUG,
            "hierarchy_header_render_completed",
            symbol=class_name,
            duration_ms=round((perf_counter() - header_gen_start) * 1000, 3),
            byte_count=len(header.encode("utf-8")),
        )
        log_event(logger, logging.INFO, "header_generation_completed", symbol=class_name)
        return header

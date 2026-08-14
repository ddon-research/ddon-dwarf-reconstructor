"""Shared hierarchy preparation helpers for header generation."""

from __future__ import annotations

import logging
from time import perf_counter

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.observability import get_logger, log_event
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import calculate_packing_info
from ..generation.runtime import GenerationRuntime
from .dwarf_lookup import GeneratorLookupService

logger = get_logger(__name__)


class HeaderGenerationSupportMixin:
    """Prepare and validate the data shared by header output modes."""

    @staticmethod
    def _find_class_with_timing(
        context: GenerationRuntime, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        started_at = perf_counter()
        result = GeneratorLookupService.find_class(context, class_name)
        log_event(
            logger,
            logging.DEBUG,
            "class_search_completed",
            symbol=class_name,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            found=result is not None,
        )
        return result

    @staticmethod
    def _expand_typedef_search(context: GenerationRuntime, full_hierarchy: bool = True) -> None:
        """Expand typedef search for hierarchy generation."""
        started_at = perf_counter()
        context.type_resolver.expand_primitive_search(full_hierarchy=full_hierarchy)
        log_event(
            logger,
            logging.DEBUG,
            "typedef_search_expanded",
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            full_hierarchy=full_hierarchy,
        )

    @staticmethod
    def _build_hierarchy_with_timing(
        context: GenerationRuntime,
        class_name: str,
        max_depth: int = 10,
        *,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build full hierarchy with dependencies and timing."""
        started_at = perf_counter()
        class_infos, hierarchy_order = (
            context.hierarchy_builder.build_full_hierarchy_with_dependencies(
                class_name,
                max_depth=max_depth,
                include_method_signatures=include_method_signatures,
            )
        )
        log_event(
            logger,
            logging.DEBUG,
            "hierarchy_build_completed",
            symbol=class_name,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            class_count=len(class_infos),
            order_count=len(hierarchy_order),
            include_method_signatures=include_method_signatures,
        )
        return class_infos, hierarchy_order

    @staticmethod
    def _validate_hierarchy(
        context: GenerationRuntime, class_infos: dict[str, ClassInfo], class_name: str
    ) -> bool:
        del context
        if not class_infos:
            log_event(logger, logging.WARNING, "hierarchy_empty", symbol=class_name)
            return False
        return True

    @staticmethod
    def _collect_typedefs_and_packing(
        context: GenerationRuntime, class_infos: dict[str, ClassInfo]
    ) -> dict[str, str]:
        """Add packing information and collect all used typedefs."""
        started_at = perf_counter()
        all_typedefs: dict[str, str] = {}
        for class_info in class_infos.values():
            if class_info.packing_info is None:
                class_info.packing_info = calculate_packing_info(class_info)
            all_typedefs.update(
                context.type_resolver.collect_used_typedefs(
                    class_info.members,
                    class_info.methods,
                    class_info.unions,
                    class_info.nested_structs,
                )
            )
        log_event(
            logger,
            logging.DEBUG,
            "packing_and_typedefs_completed",
            class_count=len(class_infos),
            typedef_count=len(all_typedefs),
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
        return all_typedefs

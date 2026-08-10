"""Multi-file header generation operations for the application generator."""

from __future__ import annotations

import logging
import os
from time import perf_counter

from ...core.observability import get_logger, log_event, log_timing
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import FileRegistry, SpecialHeaderRenderer
from .dwarf_generator_context import DwarfGeneratorContext

logger = get_logger(__name__)


class MultiFileGenerationService:
    @staticmethod
    def _header_filename(file_path: str) -> str:
        filename = os.path.basename(file_path) if file_path else "Unknown.h"
        if not filename.endswith(".h"):
            filename = filename.rsplit(".", 1)[0] + ".h"
        return filename

    @staticmethod
    def _class_header_names(classes_by_file: dict[str, list[str]]) -> dict[str, str]:
        return {
            class_name: MultiFileGenerationService._header_filename(file_path)
            for file_path, class_names in classes_by_file.items()
            for class_name in class_names
        }

    def _build_file_registry(
        self: DwarfGeneratorContext, class_infos: dict[str, ClassInfo]
    ) -> FileRegistry:
        assert self.dwarf_info is not None
        registry = FileRegistry(self.dwarf_info)
        for class_name, class_info in class_infos.items():
            if class_info.cu_offset is not None:
                registry.register_class(
                    class_name,
                    class_info.cu_offset,
                    class_info.declaration_file,
                )
        return registry

    def _render_file_headers(
        self: DwarfGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        classes_by_file: dict[str, list[str]],
        typedefs: dict[str, str],
        include_metadata: bool,
        class_header_names: dict[str, str] | None = None,
    ) -> dict[str, str]:
        assert self.header_generator is not None
        output_headers: dict[str, str] = {}
        known_header_names = class_header_names or MultiFileGenerationService._class_header_names(
            classes_by_file
        )
        for file_path, file_classes in sorted(classes_by_file.items()):
            if not file_classes:
                continue
            filename = MultiFileGenerationService._header_filename(file_path)
            file_class_infos = {
                name: info for name, info in class_infos.items() if name in file_classes
            }
            file_order = [name for name in hierarchy_order if name in file_classes]
            dependency_headers = self.header_generator.external_dependency_headers(
                class_infos,
                set(file_classes),
                known_header_names,
            )
            header = self.header_generator.generate_single_file_hierarchy_header(
                file_class_infos,
                file_order,
                file_classes[0],
                typedefs=typedefs,
                include_metadata=include_metadata,
                dependency_headers=dependency_headers,
            )
            output_headers[filename] = header
        return output_headers

    def _render_uncategorized_header(
        self: DwarfGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        uncategorized: list[str],
        typedefs: dict[str, str],
        include_metadata: bool,
        class_header_names: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not uncategorized:
            return {}
        assert self.header_generator is not None
        uncategorized_infos = {
            name: info for name, info in class_infos.items() if name in uncategorized
        }
        uncategorized_order = [name for name in hierarchy_order if name in uncategorized]
        known_header_names = class_header_names or {
            name: MultiFileGenerationService._header_filename(
                info.declaration_file or "UncategorizedDefinitions"
            )
            for name, info in class_infos.items()
        }
        dependency_headers = self.header_generator.external_dependency_headers(
            class_infos,
            set(uncategorized),
            known_header_names,
        )
        header = self.header_generator.generate_single_file_hierarchy_header(
            uncategorized_infos,
            uncategorized_order,
            "UncategorizedDefinitions",
            typedefs=typedefs,
            include_metadata=include_metadata,
            dependency_headers=dependency_headers,
        )
        return {"UncategorizedDefinitions.h": header}

    @staticmethod
    def _prepare_hierarchy(
        context: DwarfGeneratorContext, class_name: str
    ) -> tuple[dict[str, ClassInfo], list[str]] | None:
        context.workflow.expand_typedef_search(full_hierarchy=True)
        class_infos, hierarchy_order = context.workflow.build_hierarchy_with_timing(
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )
        if not context.workflow.validate_hierarchy(class_infos, class_name):
            return None
        return class_infos, hierarchy_order

    @staticmethod
    def _render_multi_file_outputs(
        context: DwarfGeneratorContext,
        class_name: str,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
    ) -> dict[str, str]:
        registry_start = perf_counter()
        file_registry = context.workflow.build_file_registry(class_infos)
        log_event(
            logger,
            logging.DEBUG,
            "file_registry_built",
            duration_ms=round((perf_counter() - registry_start) * 1000, 3),
            class_count=len(class_infos),
        )
        classes_by_file = file_registry.get_classes_by_file()
        uncategorized = file_registry.get_uncategorized_classes()
        class_header_names = MultiFileGenerationService._class_header_names(classes_by_file)
        log_event(
            logger,
            logging.DEBUG,
            "classes_organized_by_file",
            file_count=len(classes_by_file),
            uncategorized_count=len(uncategorized),
        )
        all_typedefs = context.workflow.collect_typedefs_and_packing(class_infos)
        header_start = perf_counter()
        output_headers = context.workflow.render_file_headers(
            class_infos,
            hierarchy_order,
            classes_by_file,
            all_typedefs,
            include_metadata,
            class_header_names,
        )
        output_headers.update(
            context.workflow.render_uncategorized_header(
                class_infos,
                hierarchy_order,
                uncategorized,
                all_typedefs,
                include_metadata,
                class_header_names,
            )
        )
        log_event(
            logger,
            logging.DEBUG,
            "multi_file_headers_rendered",
            symbol=class_name,
            duration_ms=round((perf_counter() - header_start) * 1000, 3),
            header_count=len(output_headers),
            total_bytes=sum(len(header.encode("utf-8")) for header in output_headers.values()),
        )
        return output_headers

    @log_timing
    def generate_multi_file_hierarchy(
        self: DwarfGeneratorContext, class_name: str, include_metadata: bool = True
    ) -> dict[str, str]:
        """Generate deterministic headers grouped by declaration file."""
        log_event(
            logger,
            logging.INFO,
            "header_generation_started",
            symbol=class_name,
            mode="full-hierarchy-multi-file",
            include_metadata=include_metadata,
        )

        prepared = MultiFileGenerationService._prepare_hierarchy(self, class_name)
        if prepared is None:
            not_found = SpecialHeaderRenderer.render_not_found(class_name)
            return {"UncategorizedDefinitions.h": not_found}
        class_infos, hierarchy_order = prepared
        output_headers = MultiFileGenerationService._render_multi_file_outputs(
            self, class_name, class_infos, hierarchy_order, include_metadata
        )
        log_event(
            logger,
            logging.INFO,
            "header_generation_completed",
            symbol=class_name,
            header_count=len(output_headers),
        )

        return output_headers

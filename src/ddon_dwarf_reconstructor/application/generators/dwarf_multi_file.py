"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

import os
from time import time

from ...domain.models.dwarf import ClassInfo
from ...domain.repositories.cache import HeaderCache
from ...domain.services.generation import FileRegistry
from ...infrastructure.logging import get_logger, log_timing
from .dwarf_generator_context import DwarfGeneratorContext

logger = get_logger(__name__)


class MultiFileGenerationMixin:
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
        cache: HeaderCache,
    ) -> dict[str, str]:
        assert self.header_generator is not None
        output_headers: dict[str, str] = {}
        for file_path, file_classes in sorted(classes_by_file.items()):
            if not file_classes:
                continue
            filename = os.path.basename(file_path) if file_path else "Unknown.h"
            if not filename.endswith(".h"):
                filename = filename.rsplit(".", 1)[0] + ".h"
            file_class_infos = {
                name: info for name, info in class_infos.items() if name in file_classes
            }
            file_order = [name for name in hierarchy_order if name in file_classes]
            header = self.header_generator.generate_single_file_hierarchy_header(
                file_class_infos,
                file_order,
                file_classes[0],
                typedefs=typedefs,
                include_metadata=include_metadata,
            )
            output_headers[filename] = header
            cache.set_header(filename, header, file_path=filename)
        return output_headers

    def _render_uncategorized_header(
        self: DwarfGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        uncategorized: list[str],
        typedefs: dict[str, str],
        include_metadata: bool,
        cache: HeaderCache,
    ) -> dict[str, str]:
        if not uncategorized:
            return {}
        assert self.header_generator is not None
        uncategorized_infos = {
            name: info for name, info in class_infos.items() if name in uncategorized
        }
        uncategorized_order = [name for name in hierarchy_order if name in uncategorized]
        header = self.header_generator.generate_single_file_hierarchy_header(
            uncategorized_infos,
            uncategorized_order,
            "UncategorizedDefinitions",
            typedefs=typedefs,
            include_metadata=include_metadata,
        )
        cache.set_header(
            "UncategorizedDefinitions.h", header, file_path="UncategorizedDefinitions.h"
        )
        return {"UncategorizedDefinitions.h": header}

    @log_timing
    def generate_multi_file_hierarchy(
        self: DwarfGeneratorContext, class_name: str, include_metadata: bool = True
    ) -> dict[str, str]:
        """Generate deterministic headers grouped by declaration file."""
        logger.info(f"Generating multi-file hierarchy for: {class_name}")

        self._expand_typedef_search(full_hierarchy=True)

        # Multi-file output is a structural closure.  Method signatures remain
        # on the declarations, but their parameter/return types must not turn
        # every method-only dependency into another full DWARF lookup.
        class_infos, hierarchy_order = self._build_hierarchy_with_timing(
            class_name,
            max_depth=10,
            include_method_signatures=False,
        )

        # Step 3: Validate hierarchy
        if not self._validate_hierarchy(class_infos, class_name):
            not_found = self._generate_not_found_header(class_name)
            return {"UncategorizedDefinitions.h": not_found}

        registry_start = time()
        file_registry = self._build_file_registry(class_infos)
        registry_elapsed = time() - registry_start
        logger.debug(f"FileRegistry built in {registry_elapsed:.3f}s")

        # Organize classes by file
        classes_by_file = file_registry.get_classes_by_file()
        uncategorized = file_registry.get_uncategorized_classes()

        logger.info(
            f"Classes organized by file: {len(classes_by_file)} files, "
            f"{len(uncategorized)} uncategorized"
        )

        # Initialize header cache
        cache = HeaderCache(str(self.elf_path))

        # Step 4: Add packing info and collect typedefs
        all_typedefs = self._collect_typedefs_and_packing(class_infos)

        header_gen_start = time()
        output_headers = self._render_file_headers(
            class_infos,
            hierarchy_order,
            classes_by_file,
            all_typedefs,
            include_metadata,
            cache,
        )
        output_headers.update(
            self._render_uncategorized_header(
                class_infos,
                hierarchy_order,
                uncategorized,
                all_typedefs,
                include_metadata,
                cache,
            )
        )

        header_gen_elapsed = time() - header_gen_start
        logger.debug(f"Multi-file hierarchy generation completed in {header_gen_elapsed:.3f}s")

        # Save cache
        cache.save()

        logger.info(
            f"Multi-file hierarchy generated: {len(output_headers)} headers, "
            f"{sum(len(h) for h in output_headers.values())} total bytes"
        )

        return output_headers

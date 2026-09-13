"""Multi-file header generation operations for the application generator."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from time import perf_counter

from ...core.observability import get_logger, log_event, log_timing
from ...core.path_policy import create_header_filename
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import FileRegistry, SpecialHeaderRenderer
from ...domain.services.generation.header_dependency_plan import HeaderDependencyPlan
from ..generation.runtime import GenerationRuntime
from .dwarf_header_generation import HeaderGenerationService
from .dwarf_lookup import GeneratorLookupService

logger = get_logger(__name__)


class MultiFileGenerationService:
    @staticmethod
    def _namespace_headers(context: GenerationRuntime, class_name: str) -> dict[str, str] | None:
        """Render a namespace root without sending it through class hierarchy parsing."""
        result = GeneratorLookupService.find_class(context, class_name)
        if result is None:
            return None
        cu, die = result
        if not GeneratorLookupService.is_namespace(context, die):
            return None
        return {
            create_header_filename(class_name): SpecialHeaderRenderer.render_namespace(
                class_name, cu, die
            )
        }

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

    @staticmethod
    def _build_file_registry(
        context: GenerationRuntime, class_infos: dict[str, ClassInfo]
    ) -> FileRegistry:
        registry = FileRegistry(context.dwarf_info)
        for class_name, class_info in class_infos.items():
            if class_info.cu_offset is not None:
                registry.register_class(
                    class_name,
                    class_info.cu_offset,
                    class_info.declaration_file,
                )
        return registry

    @staticmethod
    def _render_file_headers(
        context: GenerationRuntime,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        classes_by_file: dict[str, list[str]],
        typedefs: dict[str, str],
        include_metadata: bool,
        class_header_names: dict[str, str] | None = None,
        allow_cyclic_dependencies: bool = False,
        dependency_headers_by_file: dict[str, dict[str, str]] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
        target_classes_by_file: dict[str, str] | None = None,
        guard_suffixes_by_file: dict[str, str] | None = None,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> dict[str, str]:
        output_headers: dict[str, str] = {}
        known_header_names = class_header_names or MultiFileGenerationService._class_header_names(
            classes_by_file
        )
        for file_path, file_classes in sorted(classes_by_file.items()):
            if not file_classes:
                continue
            filename = MultiFileGenerationService._header_filename(file_path)
            file_class_infos = MultiFileGenerationService._class_infos_for_file(
                class_infos, file_classes
            )
            file_order = MultiFileGenerationService._order_for_file(hierarchy_order, file_classes)
            dependency_headers = MultiFileGenerationService._dependency_headers_for_file(
                context,
                file_path,
                file_classes,
                known_header_names,
                typedefs,
                dependency_headers_by_file,
                class_infos,
            )
            header = MultiFileGenerationService._render_one_file_header(
                context,
                file_class_infos,
                file_order,
                (target_classes_by_file or {}).get(file_path, file_classes[0]),
                typedefs,
                include_metadata,
                dependency_headers,
                base_type_infos or class_infos,
                allow_cyclic_dependencies,
                (guard_suffixes_by_file or {}).get(file_path, "_H"),
                dependency_plan=dependency_plan,
            )
            output_headers[filename] = header
        return output_headers

    @staticmethod
    def _class_infos_for_file(
        class_infos: dict[str, ClassInfo], file_classes: list[str]
    ) -> dict[str, ClassInfo]:
        return {name: info for name, info in class_infos.items() if name in file_classes}

    @staticmethod
    def _order_for_file(hierarchy_order: list[str], file_classes: list[str]) -> list[str]:
        return [name for name in hierarchy_order if name in file_classes]

    @staticmethod
    def _dependency_headers_for_file(
        context: GenerationRuntime,
        file_path: str,
        file_classes: list[str],
        known_header_names: dict[str, str],
        typedefs: dict[str, str],
        dependency_headers_by_file: dict[str, dict[str, str]] | None,
        class_infos: dict[str, ClassInfo],
    ) -> dict[str, str]:
        if dependency_headers_by_file is not None and file_path in dependency_headers_by_file:
            return dependency_headers_by_file[file_path]
        return context.header_renderer.external_dependency_headers(
            class_infos, set(file_classes), known_header_names, typedefs
        )

    @staticmethod
    def _render_one_file_header(
        context: GenerationRuntime,
        file_class_infos: dict[str, ClassInfo],
        file_order: list[str],
        target: str,
        typedefs: dict[str, str],
        include_metadata: bool,
        dependency_headers: dict[str, str],
        base_type_infos: dict[str, ClassInfo],
        allow_cyclic_dependencies: bool,
        guard_suffix: str = "_H",
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> str:
        return context.header_renderer.generate_single_file_hierarchy_header(
            file_class_infos,
            file_order,
            target,
            typedefs=typedefs,
            include_metadata=include_metadata,
            dependency_headers=dependency_headers,
            base_type_infos=base_type_infos,
            allow_cyclic_dependencies=allow_cyclic_dependencies,
            guard_suffix=guard_suffix,
            dependency_plan=dependency_plan,
        )

    @staticmethod
    def _render_uncategorized_header(
        context: GenerationRuntime,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        uncategorized: list[str],
        typedefs: dict[str, str],
        include_metadata: bool,
        class_header_names: dict[str, str] | None = None,
        dependency_headers: Mapping[str, dict[str, str]] | None = None,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> dict[str, str]:
        if not uncategorized:
            return {}
        uncategorized_infos = MultiFileGenerationService._class_infos_for_file(
            class_infos, uncategorized
        )
        uncategorized_order = MultiFileGenerationService._order_for_file(
            hierarchy_order, uncategorized
        )
        known_header_names = MultiFileGenerationService._uncategorized_header_names(
            class_infos, class_header_names
        )
        planned_headers = MultiFileGenerationService._uncategorized_dependency_headers(
            context,
            class_infos,
            uncategorized,
            known_header_names,
            typedefs,
            dependency_headers,
        )
        header = context.header_renderer.generate_single_file_hierarchy_header(
            uncategorized_infos,
            uncategorized_order,
            "UncategorizedDefinitions",
            typedefs=typedefs,
            include_metadata=include_metadata,
            dependency_headers=planned_headers,
            base_type_infos=class_infos,
            dependency_plan=dependency_plan,
        )
        return {"UncategorizedDefinitions.h": header}

    @staticmethod
    def _uncategorized_header_names(
        class_infos: dict[str, ClassInfo], class_header_names: dict[str, str] | None
    ) -> dict[str, str]:
        if class_header_names is not None:
            return class_header_names
        return {
            name: MultiFileGenerationService._header_filename(
                info.declaration_file or "UncategorizedDefinitions"
            )
            for name, info in class_infos.items()
        }

    @staticmethod
    def _uncategorized_dependency_headers(
        context: GenerationRuntime,
        class_infos: dict[str, ClassInfo],
        uncategorized: list[str],
        known_header_names: dict[str, str],
        typedefs: dict[str, str],
        dependency_headers: Mapping[str, dict[str, str]] | None,
    ) -> dict[str, str]:
        if dependency_headers is not None:
            planned = dependency_headers.get("UncategorizedDefinitions.h")
            if planned is not None:
                return planned
        return context.header_renderer.external_dependency_headers(
            class_infos, set(uncategorized), known_header_names, typedefs
        )

    @staticmethod
    def _plan_dependency_headers(
        context: GenerationRuntime,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        groups_by_file: Mapping[str, set[str]],
        header_names_by_file: Mapping[str, Mapping[str, str]],
        typedefs_by_file: Mapping[str, Mapping[str, str]],
        typedefs: dict[str, str],
    ) -> tuple[dict[str, dict[str, str]], HeaderDependencyPlan | None]:
        """Plan all file dependencies through one shared graph and name index."""
        dependency_plan: HeaderDependencyPlan | None = None
        builder = getattr(context.header_renderer, "build_dependency_plan", None)
        if callable(builder):
            candidate = builder(class_infos, hierarchy_order, typedefs)
            if isinstance(candidate, HeaderDependencyPlan):
                dependency_plan = candidate
        planner = getattr(
            context.header_renderer, "external_dependency_headers_for_group_specs", None
        )
        if not callable(planner):
            return {}, dependency_plan
        planned = planner(
            class_infos,
            groups_by_file,
            header_names_by_file,
            typedefs_by_file,
            dependency_plan=dependency_plan,
        )
        if not isinstance(planned, Mapping) or not all(
            isinstance(value, Mapping) for value in planned.values()
        ):
            return {}, dependency_plan
        return {
            str(group_id): dict(headers) for group_id, headers in planned.items()
        }, dependency_plan

    @staticmethod
    def _prepare_multi_file_plan(
        context: GenerationRuntime,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        classes_by_file: dict[str, list[str]],
        uncategorized: list[str],
    ) -> tuple[
        dict[str, str],
        dict[str, str],
        dict[str, dict[str, str]],
        HeaderDependencyPlan | None,
    ]:
        class_header_names = MultiFileGenerationService._class_header_names(classes_by_file)
        uncategorized_header = MultiFileGenerationService._header_filename(
            "UncategorizedDefinitions"
        )
        for class_name in uncategorized:
            class_header_names.setdefault(class_name, uncategorized_header)
        all_typedefs = HeaderGenerationService._collect_typedefs_and_packing(context, class_infos)
        groups_for_planning = {
            file_path: set(file_classes)
            for file_path, file_classes in classes_by_file.items()
            if file_classes
        }
        if uncategorized:
            groups_for_planning["UncategorizedDefinitions.h"] = set(uncategorized)
        header_names_for_planning = {
            file_path: dict(class_header_names) for file_path in groups_for_planning
        }
        typedefs_for_planning = dict.fromkeys(groups_for_planning, all_typedefs)
        dependency_headers_by_file, dependency_plan = (
            MultiFileGenerationService._plan_dependency_headers(
                context,
                class_infos,
                hierarchy_order,
                groups_for_planning,
                header_names_for_planning,
                typedefs_for_planning,
                all_typedefs,
            )
        )
        return (
            class_header_names,
            all_typedefs,
            dependency_headers_by_file,
            dependency_plan,
        )

    @staticmethod
    def _prepare_hierarchy(
        context: GenerationRuntime, class_name: str
    ) -> tuple[dict[str, ClassInfo], list[str]] | None:
        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)
        class_infos, hierarchy_order = HeaderGenerationService._build_hierarchy_with_timing(
            context,
            class_name,
            max_depth=10,
            include_method_signatures=True,
        )
        if not HeaderGenerationService._validate_hierarchy(context, class_infos, class_name):
            return None
        return class_infos, hierarchy_order

    @staticmethod
    def _render_multi_file_outputs(
        context: GenerationRuntime,
        class_name: str,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
    ) -> dict[str, str]:
        registry_start = perf_counter()
        file_registry = MultiFileGenerationService._build_file_registry(context, class_infos)
        log_event(
            logger,
            logging.DEBUG,
            "file_registry_built",
            duration_ms=round((perf_counter() - registry_start) * 1000, 3),
            class_count=len(class_infos),
        )
        classes_by_file = file_registry.get_classes_by_file()
        uncategorized = file_registry.get_uncategorized_classes()
        log_event(
            logger,
            logging.DEBUG,
            "classes_organized_by_file",
            file_count=len(classes_by_file),
            uncategorized_count=len(uncategorized),
        )
        (
            class_header_names,
            all_typedefs,
            dependency_headers_by_file,
            dependency_plan,
        ) = MultiFileGenerationService._prepare_multi_file_plan(
            context,
            class_infos,
            hierarchy_order,
            classes_by_file,
            uncategorized,
        )
        header_start = perf_counter()
        output_headers = MultiFileGenerationService._render_file_headers(
            context,
            class_infos,
            hierarchy_order,
            classes_by_file,
            all_typedefs,
            include_metadata,
            class_header_names,
            dependency_headers_by_file=dependency_headers_by_file,
            dependency_plan=dependency_plan,
        )
        output_headers.update(
            MultiFileGenerationService._render_uncategorized_header(
                context,
                class_infos,
                hierarchy_order,
                uncategorized,
                all_typedefs,
                include_metadata,
                class_header_names,
                dependency_headers_by_file,
                dependency_plan,
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

    @staticmethod
    @log_timing
    def generate_multi_file_hierarchy(
        context: GenerationRuntime, class_name: str, include_metadata: bool = True
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

        namespace_headers = MultiFileGenerationService._namespace_headers(context, class_name)
        if namespace_headers is not None:
            log_event(
                logger,
                logging.INFO,
                "namespace_header_generation",
                symbol=class_name,
                header_count=len(namespace_headers),
            )
            return namespace_headers

        prepared = MultiFileGenerationService._prepare_hierarchy(context, class_name)
        if prepared is None:
            not_found = SpecialHeaderRenderer.render_not_found(class_name)
            return {"UncategorizedDefinitions.h": not_found}
        class_infos, hierarchy_order = prepared
        output_headers = MultiFileGenerationService._render_multi_file_outputs(
            context, class_name, class_infos, hierarchy_order, include_metadata
        )
        log_event(
            logger,
            logging.INFO,
            "header_generation_completed",
            symbol=class_name,
            header_count=len(output_headers),
        )

        return output_headers

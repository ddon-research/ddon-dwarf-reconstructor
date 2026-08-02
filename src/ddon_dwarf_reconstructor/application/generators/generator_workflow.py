"""Composed generator workflow operations."""

from __future__ import annotations

from pathlib import Path

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation.file_registry import FileRegistry
from .dwarf_generator_context import DwarfGeneratorContext
from .dwarf_header_generation import HeaderGenerationService
from .dwarf_knowledge import KnowledgeExportService
from .dwarf_lookup import GeneratorLookupService
from .dwarf_multi_file import MultiFileGenerationService


class GeneratorWorkflow:
    """Compose generator responsibilities around one application context."""

    def __init__(self, context: DwarfGeneratorContext) -> None:
        self.context = context

    def find_class(self, class_name: str) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        return GeneratorLookupService.find_class(self.context, class_name)

    def is_namespace(self, die: DwarfEntry) -> bool:
        return GeneratorLookupService.is_namespace(self.context, die)

    def parse_class_info(self, cu: DwarfCompilationUnit, class_die: DwarfEntry) -> ClassInfo:
        return GeneratorLookupService.parse_class_info(self.context, cu, class_die)

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
        return GeneratorLookupService.build_inheritance_hierarchy(self.context, class_name)

    def generate_header(self, class_name: str, include_metadata: bool = True) -> str:
        return HeaderGenerationService.generate_header(self.context, class_name, include_metadata)

    def expand_typedef_search(self, full_hierarchy: bool = True) -> None:
        HeaderGenerationService._expand_typedef_search(self.context, full_hierarchy)

    def build_hierarchy_with_timing(
        self, class_name: str, max_depth: int = 10, *, include_method_signatures: bool = True
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        return HeaderGenerationService._build_hierarchy_with_timing(
            self.context,
            class_name,
            max_depth,
            include_method_signatures=include_method_signatures,
        )

    def validate_hierarchy(self, class_infos: dict[str, ClassInfo], class_name: str) -> bool:
        return HeaderGenerationService._validate_hierarchy(self.context, class_infos, class_name)

    def collect_typedefs_and_packing(self, class_infos: dict[str, ClassInfo]) -> dict[str, str]:
        return HeaderGenerationService._collect_typedefs_and_packing(self.context, class_infos)

    def generate_complete_hierarchy_header(
        self, class_name: str, include_metadata: bool = True
    ) -> str:
        return HeaderGenerationService.generate_complete_hierarchy_header(
            self.context, class_name, include_metadata
        )

    def build_file_registry(self, class_infos: dict[str, ClassInfo]) -> FileRegistry:
        return MultiFileGenerationService._build_file_registry(self.context, class_infos)

    def render_file_headers(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        classes_by_file: dict[str, list[str]],
        typedefs: dict[str, str],
        include_metadata: bool,
    ) -> dict[str, str]:
        return MultiFileGenerationService._render_file_headers(
            self.context,
            class_infos,
            hierarchy_order,
            classes_by_file,
            typedefs,
            include_metadata,
        )

    def render_uncategorized_header(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        uncategorized: list[str],
        typedefs: dict[str, str],
        include_metadata: bool,
    ) -> dict[str, str]:
        return MultiFileGenerationService._render_uncategorized_header(
            self.context,
            class_infos,
            hierarchy_order,
            uncategorized,
            typedefs,
            include_metadata,
        )

    def generate_multi_file_hierarchy(
        self, class_name: str, include_metadata: bool = True
    ) -> dict[str, str]:
        return MultiFileGenerationService.generate_multi_file_hierarchy(
            self.context, class_name, include_metadata
        )

    def export_knowledge_graph(
        self,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> Path:
        return KnowledgeExportService.export_knowledge_graph(
            self.context,
            root_symbol,
            output_dir,
            build_id,
            orbis_objdump_path=orbis_objdump_path,
        )

"""Typed collaboration contract for the application generator mixins."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ...domain.models.dwarf import ClassInfo
from ...domain.ports.class_parser import ClassParserPort
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.dump_lookup import DumpLookupFactory
from ...domain.ports.type_resolution import TypeResolverPort
from ...domain.repositories.cache import HeaderCache
from ...domain.services.generation import FileRegistry, HeaderGenerator, HierarchyBuilder
from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService
from ...infrastructure.elf_platform import ELFPlatform
from .generation_contracts import GenerationRequest, HeaderBundle


class DwarfGeneratorContext(Protocol):
    """State and operations shared by the generator responsibilities."""

    elf_path: Path
    platform: ELFPlatform
    dwarf_info: DWARFInfo | None
    class_parser: ClassParserPort | None
    type_resolver: TypeResolverPort | None
    header_generator: HeaderGenerator | None
    lazy_index: LazyDwarfIndexService | None
    hierarchy_builder: HierarchyBuilder | None
    dump_lookup_factory: DumpLookupFactory | None
    disassembly_factory: DisassemblyProducerFactory | None

    def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def is_namespace(self, die: DIE) -> bool: ...

    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo: ...

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]: ...

    def generate_header(self, class_name: str, include_metadata: bool = True) -> str: ...

    def generate_bundle(self, request: GenerationRequest) -> HeaderBundle: ...

    def generate_complete_hierarchy_header(
        self, class_name: str, include_metadata: bool = True
    ) -> str: ...

    def generate_multi_file_hierarchy(
        self, class_name: str, include_metadata: bool = True
    ) -> dict[str, str]: ...

    def export_knowledge_graph(
        self,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> Path: ...

    def _generate_not_found_header(self, class_name: str) -> str: ...

    def _generate_namespace_header(
        self, namespace_name: str, cu: CompileUnit, namespace_die: DIE
    ) -> str: ...

    def _expand_typedef_search(self, full_hierarchy: bool = True) -> None: ...

    def _build_hierarchy_with_timing(
        self,
        class_name: str,
        max_depth: int = 10,
        *,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...

    def _validate_hierarchy(self, class_infos: dict[str, ClassInfo], class_name: str) -> bool: ...

    def _collect_typedefs_and_packing(
        self, class_infos: dict[str, ClassInfo]
    ) -> dict[str, str]: ...

    def _build_file_registry(self, class_infos: dict[str, ClassInfo]) -> FileRegistry: ...

    def _render_file_headers(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        classes_by_file: dict[str, list[str]],
        typedefs: dict[str, str],
        include_metadata: bool,
        cache: HeaderCache,
    ) -> dict[str, str]: ...

    def _render_uncategorized_header(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        uncategorized: list[str],
        typedefs: dict[str, str],
        include_metadata: bool,
        cache: HeaderCache,
    ) -> dict[str, str]: ...

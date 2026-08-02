#!/usr/bin/env python3

"""DWARF-to-C++ header generator orchestrator (Application Layer).

This is the main generator that orchestrates the modular components:
- TypeResolver: Type resolution and typedef handling
- ClassParser: DWARF class parsing
- HeaderGenerator: C++ header generation
- HierarchyBuilder: Inheritance hierarchy management
- PackingAnalyzer: Struct packing analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.path_policy import create_header_filename
from ...domain.models.dwarf import ClassInfo
from ...domain.ports.class_parser import ClassParserPort
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.dump_lookup import DumpLookupFactory
from ...domain.ports.source_identity import SourceHashPort, SourceIdentityPort
from ...domain.ports.type_resolution import TypeResolverPort
from ...domain.services.generation import HeaderGenerator, HierarchyBuilder
from .dwarf_generator_setup import DwarfGeneratorSetup
from .generation_contracts import GenerationRequest, HeaderBundle
from .generator_workflow import GeneratorWorkflow
from .session import DwarfSessionFactory

if TYPE_CHECKING:
    from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService


class DwarfGenerator:
    """Coordinate one ELF/DWARF session and its typed generation workflow."""

    def __init__(
        self,
        elf_path: Path,
        session_factory: DwarfSessionFactory,
        exhaustive_search: bool = False,
        dwarf_dump_path: Path | None = None,
        dwarf_index_path: Path | None = None,
        resolve_param_names: bool = False,
        dump_lookup_factory: DumpLookupFactory | None = None,
        disassembly_factory: DisassemblyProducerFactory | None = None,
        cache_file: Path | None = None,
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
        search_timeout: float = 1.0,
        source_hash: SourceHashPort | None = None,
        source_identity: SourceIdentityPort | None = None,
    ):
        """Initialize generator with ELF file path using lazy loading.

        Args:
            elf_path: Path to ELF file containing DWARF information
            session_factory: Composition-root factory for the ELF/DWARF session
            exhaustive_search: Enable exhaustive search mode (scan all CUs for best definition)
            dwarf_dump_path: Optional path to compressed llvm-dwarfdump .zst file for fast lookups
            dwarf_index_path: Optional explicit SQLite sidecar path for the dump index
            resolve_param_names: Enable method implementation search for parameter names (expensive)
        """
        self.session = session_factory(elf_path)
        self.elf_path = elf_path
        self.dwarf_info = None
        self.platform = self.session.platform
        self.exhaustive_search = exhaustive_search
        self._configured_dwarf_dump_path = dwarf_dump_path
        self.dwarf_dump_path = self._resolve_dwarf_dump_path()
        self.dwarf_index_path = dwarf_index_path
        self.resolve_param_names = resolve_param_names
        self.dump_lookup_factory = dump_lookup_factory
        self.disassembly_factory = disassembly_factory
        self.cache_file = cache_file
        self.die_cache_size = die_cache_size
        self.type_cache_size = type_cache_size
        self.search_timeout = search_timeout
        self.source_hash = source_hash
        self.source_identity = source_identity
        self.workflow = GeneratorWorkflow(self)
        self.type_resolver: TypeResolverPort | None = None
        self.class_parser: ClassParserPort | None = None
        self.header_generator: HeaderGenerator | None = None
        self.lazy_index: LazyDwarfIndexService | None = None
        self.hierarchy_builder: HierarchyBuilder | None = None

    def _resolve_dwarf_dump_path(self, explicit_path: Path | None = None) -> Path | None:
        return DwarfGeneratorSetup._resolve_dwarf_dump_path(self, explicit_path)

    def __enter__(self) -> DwarfGenerator:
        return DwarfGeneratorSetup.enter(self)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        DwarfGeneratorSetup.exit(self, exc_type, exc_val, exc_tb)

    def _initialize_components(self) -> None:
        DwarfGeneratorSetup.initialize_components(self)

    def generate(self, symbol: str, **options: bool) -> str:
        """Generate one header using a typed request."""
        request = GenerationRequest(
            symbol=symbol,
            full_hierarchy=options.get("full_hierarchy", False),
            single_file=True,
            include_metadata=not options.get("no_metadata", False),
        )
        return self.generate_bundle(request).only()

    def find_class(self, class_name: str) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        return self.workflow.find_class(class_name)

    def is_namespace(self, die: DwarfEntry) -> bool:
        return self.workflow.is_namespace(die)

    def parse_class_info(self, cu: DwarfCompilationUnit, class_die: DwarfEntry) -> ClassInfo:
        return self.workflow.parse_class_info(cu, class_die)

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
        return self.workflow.build_inheritance_hierarchy(class_name)

    def generate_header(self, class_name: str, include_metadata: bool = True) -> str:
        return self.workflow.generate_header(class_name, include_metadata)

    def generate_complete_hierarchy_header(
        self, class_name: str, include_metadata: bool = True
    ) -> str:
        return self.workflow.generate_complete_hierarchy_header(class_name, include_metadata)

    def generate_multi_file_hierarchy(
        self, class_name: str, include_metadata: bool = True
    ) -> dict[str, str]:
        return self.workflow.generate_multi_file_hierarchy(class_name, include_metadata)

    def export_knowledge_graph(
        self,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> Path:
        return self.workflow.export_knowledge_graph(
            root_symbol,
            output_dir,
            build_id,
            orbis_objdump_path=orbis_objdump_path,
        )

    def generate_bundle(self, request: GenerationRequest) -> HeaderBundle:
        """Run one typed workflow and adapt its result to a header bundle."""
        if request.full_hierarchy and not request.single_file:
            return HeaderBundle(
                self.workflow.generate_multi_file_hierarchy(
                    request.symbol, request.include_metadata
                )
            )
        if request.full_hierarchy:
            content = self.workflow.generate_complete_hierarchy_header(
                request.symbol, request.include_metadata
            )
        else:
            content = self.workflow.generate_header(request.symbol, request.include_metadata)
        return HeaderBundle({create_header_filename(request.symbol): content})

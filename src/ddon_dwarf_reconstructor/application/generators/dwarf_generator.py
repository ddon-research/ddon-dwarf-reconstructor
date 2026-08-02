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

import os
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, cast

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.observability import get_logger
from ...core.path_policy import create_header_filename
from ...domain.ports.class_parser import ClassParserPort
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.dump_lookup import DumpLookupFactory
from ...domain.ports.source_identity import SourceHashPort
from ...domain.ports.type_resolution import TypeResolverPort
from ...domain.services.generation import (
    HeaderGenerator,
    HierarchyBuilder,
    SpecialHeaderRenderer,
)
from ...generators.base_generator import BaseGenerator
from .dwarf_generator_context import DwarfGeneratorContext
from .dwarf_header_generation import HeaderGenerationMixin
from .dwarf_knowledge import KnowledgeExportMixin
from .dwarf_lookup import GeneratorLookupMixin
from .dwarf_multi_file import MultiFileGenerationMixin
from .generation_contracts import GenerationRequest, HeaderBundle

if TYPE_CHECKING:
    from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService

logger = get_logger(__name__)


class DwarfGenerator(
    GeneratorLookupMixin,
    HeaderGenerationMixin,
    MultiFileGenerationMixin,
    KnowledgeExportMixin,
    BaseGenerator,
    DwarfGeneratorContext,
):
    """DWARF-to-C++ header generator using modular architecture.

    This refactored implementation delegates responsibilities to specialized modules:
    - Parsing is handled by ClassParser
    - Type resolution by TypeResolver
    - Header generation by HeaderGenerator
    - Hierarchy management by HierarchyBuilder
    """

    def __init__(
        self,
        elf_path: Path,
        exhaustive_search: bool = False,
        dwarf_dump_path: Path | None = None,
        dwarf_index_path: Path | None = None,
        resolve_param_names: bool = False,
        dump_lookup_factory: DumpLookupFactory | None = None,
        disassembly_factory: DisassemblyProducerFactory | None = None,
        cache_file: Path | None = None,
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
        source_hash: SourceHashPort | None = None,
    ):
        """Initialize generator with ELF file path using lazy loading.

        Args:
            elf_path: Path to ELF file containing DWARF information
            exhaustive_search: Enable exhaustive search mode (scan all CUs for best definition)
            dwarf_dump_path: Optional path to compressed llvm-dwarfdump .zst file for fast lookups
            dwarf_index_path: Optional explicit SQLite sidecar path for the dump index
            resolve_param_names: Enable method implementation search for parameter names (expensive)
        """
        super().__init__(elf_path)
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
        self.source_hash = source_hash
        self.type_resolver: TypeResolverPort | None = None
        self.class_parser: ClassParserPort | None = None
        self.header_generator: HeaderGenerator | None = None
        self.lazy_index: LazyDwarfIndexService | None = None
        self.hierarchy_builder: HierarchyBuilder | None = None

    def _resolve_dwarf_dump_path(self, explicit_path: Path | None = None) -> Path | None:
        """Resolve the compressed DWARF dump path using documented precedence.

        Args:
            explicit_path: Optional path supplied by the caller.

        Returns:
            The first existing candidate, or ``None`` when no dump is available.
        """
        if explicit_path is None:
            explicit_path = self._configured_dwarf_dump_path

        if explicit_path is not None:
            return explicit_path

        if not self.exhaustive_search:
            return None

        environment_path = os.getenv("DDON_DWARF_DUMP_PATH")
        if environment_path:
            candidate = Path(environment_path)
            if candidate.exists():
                return candidate

        sibling_path = self.elf_path.with_name(f"{self.elf_path.name}.llvmdwarfdump.zst")
        if sibling_path.exists():
            return sibling_path

        return None

    def __enter__(self) -> DwarfGenerator:
        """Context manager entry - initializes all modules."""
        super().__enter__()

        # Initialize modules (dwarf_info is guaranteed non-None after __enter__)
        initialization_start = time()
        assert self.dwarf_info is not None

        # Initialize components with lazy loading (only approach)
        self._initialize_components()

        total_elapsed = time() - initialization_start
        logger.info(f"DwarfGenerator initialized with modular architecture in {total_elapsed:.3f}s")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Context manager exit - saves cache and closes resources."""
        # Save cache before parent cleanup
        if self.lazy_index is not None:
            logger.debug("Saving DWARF cache to disk")
            self.lazy_index.save_cache()
            logger.info("DWARF cache saved successfully")

        # Call parent cleanup
        super().__exit__(exc_type, exc_val, exc_tb)

    def _initialize_components(self) -> None:
        """Initialize components with lazy loading and memory monitoring."""
        from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService
        from ...domain.services.parsing import ClassParser
        from ...domain.services.parsing.type_resolver import LazyTypeResolver

        assert self.dwarf_info is not None, "dwarf_info must be initialized"
        cache_file = self.cache_file or Path(".dwarf_cache.json")

        # Initialize lazy index
        lazy_start = time()
        self.lazy_index = LazyDwarfIndexService(
            self.dwarf_info,
            str(cache_file),
            die_cache_size=self.die_cache_size,
            type_cache_size=self.type_cache_size,
            source_file_path=self.elf_path,
        )
        lazy_elapsed = time() - lazy_start
        logger.debug(f"LazyDwarfIndex initialization: {lazy_elapsed:.3f}s")

        # Initialize lazy type resolver (the only type resolver now)
        resolver_start = time()
        self.type_resolver = LazyTypeResolver(self.dwarf_info, self.lazy_index)
        resolver_elapsed = time() - resolver_start
        logger.debug(f"LazyTypeResolver initialization: {resolver_elapsed:.3f}s")

        # Initialize class parser with lazy index
        parser_start = time()
        self.class_parser = cast(
            ClassParserPort,
            ClassParser(
                self.type_resolver,
                self.dwarf_info,
                self.lazy_index,
                exhaustive_search=self.exhaustive_search,
                dwarf_dump_path=self.dwarf_dump_path,
                dwarf_index_path=self.dwarf_index_path,
                resolve_param_names=self.resolve_param_names,
                dump_parser=(
                    self.dump_lookup_factory(self.dwarf_dump_path, self.dwarf_index_path)
                    if self.dump_lookup_factory is not None and self.dwarf_dump_path is not None
                    else None
                ),
            ),
        )
        parser_elapsed = time() - parser_start
        logger.debug(f"ClassParser with lazy loading initialization: {parser_elapsed:.3f}s")

        # Initialize header generator with DWARF index
        header_start = time()
        parser = self.class_parser
        assert parser is not None
        self.header_generator = HeaderGenerator(self.lazy_index, parser)
        header_elapsed = time() - header_start
        logger.debug(f"HeaderGenerator initialization: {header_elapsed:.3f}s")

        # Initialize hierarchy builder
        hierarchy_start = time()
        self.hierarchy_builder = HierarchyBuilder(parser, self.lazy_index)
        hierarchy_elapsed = time() - hierarchy_start
        logger.debug(f"HierarchyBuilder initialization: {hierarchy_elapsed:.3f}s")

    def generate(self, symbol: str, **options: bool) -> str:
        """Generate C++ header for the specified symbol.

        Args:
            symbol: Target symbol name to generate header for
            **options: Generation options
                - full_hierarchy (bool): Generate complete inheritance hierarchy
                - no_metadata (bool): Skip DWARF metadata comments

        Returns:
            Generated C++ header as string
        """
        request = GenerationRequest(
            symbol=symbol,
            full_hierarchy=options.get("full_hierarchy", False),
            single_file=True,
            include_metadata=not options.get("no_metadata", False),
        )
        return self.generate_bundle(request).only()

    def generate_bundle(self, request: GenerationRequest) -> HeaderBundle:
        """Run one typed workflow and adapt its result to a header bundle."""
        if request.full_hierarchy and not request.single_file:
            return HeaderBundle(
                self.generate_multi_file_hierarchy(request.symbol, request.include_metadata)
            )
        if request.full_hierarchy:
            content = self.generate_complete_hierarchy_header(
                request.symbol, request.include_metadata
            )
        else:
            content = self.generate_header(request.symbol, request.include_metadata)
        return HeaderBundle({create_header_filename(request.symbol): content})

    def _generate_not_found_header(self, class_name: str) -> str:
        """Generate a deterministic placeholder for an unresolved symbol."""
        return SpecialHeaderRenderer.render_not_found(class_name)

    def _generate_namespace_header(
        self, namespace_name: str, cu: DwarfCompilationUnit, namespace_die: DwarfEntry
    ) -> str:
        """Generate a namespace header through the shared renderer."""
        return SpecialHeaderRenderer.render_namespace(namespace_name, cu, namespace_die)

"""Typed construction of the components used by one generation session."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from ...core.dwarf import DwarfInfo
from ...core.observability import get_logger, log_event
from ...core.platform import ELFPlatform
from ...domain.ports.class_parser import ClassParserPort
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.dwarf_lookup import DwarfLookupPort
from ...domain.ports.source_identity import SourceHashPort, SourceIdentityPort
from ...domain.ports.type_resolution import TypeResolverPort
from ...domain.ports.validation_dump import ValidationDumpFactory
from ...domain.services.generation import HeaderRenderer, HierarchyBuilder
from ...domain.services.parsing import ClassParser
from ...domain.services.parsing.type_resolver import LazyTypeResolver
from ..generators.session import DwarfSession

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GenerationComponentOptions:
    """Immutable inputs for constructing one generation component graph."""

    elf_path: Path
    exhaustive_search: bool = False
    dwarf_dump_path: Path | None = None
    dwarf_index_path: Path | None = None
    resolve_param_names: bool = False
    dump_lookup_factory: ValidationDumpFactory | None = None
    disassembly_factory: DisassemblyProducerFactory | None = None
    cache_file: Path | None = None
    die_cache_size: int = 10000
    type_cache_size: int = 5000
    search_timeout: float = 1.0
    source_identity: SourceIdentityPort | None = None
    source_hash: SourceHashPort | None = None

    def __post_init__(self) -> None:
        """Reject validation-dump combinations that the runtime cannot honor."""
        if self.dwarf_index_path is not None and self.dwarf_dump_path is None:
            raise ValueError("dwarf_index_path requires an explicit dwarf_dump_path")
        if self.dwarf_dump_path is not None and self.dump_lookup_factory is None:
            raise ValueError("dwarf_dump_path requires a validation dump lookup factory")


@dataclass(frozen=True, slots=True)
class GenerationRuntime:
    """Ready-to-use, non-optional component graph for one open session."""

    elf_path: Path
    dwarf_info: DwarfInfo
    platform: ELFPlatform
    lazy_index: DwarfLookupPort
    type_resolver: TypeResolverPort
    class_parser: ClassParserPort
    header_renderer: HeaderRenderer
    hierarchy_builder: HierarchyBuilder
    dump_lookup_factory: ValidationDumpFactory | None
    disassembly_factory: DisassemblyProducerFactory | None
    source_hash: SourceHashPort | None
    source_identity: SourceIdentityPort | None


def resolve_explicit_validation_dump(
    configured_path: Path | None,
    explicit_path: Path | None = None,
) -> Path | None:
    """Resolve only an explicitly supplied legacy validation dump."""
    return explicit_path or configured_path


def build_generation_runtime(
    session: DwarfSession,
    options: GenerationComponentOptions,
) -> GenerationRuntime:
    """Build all generation collaborators from one opened session."""
    dwarf_info = session.dwarf_info
    if dwarf_info is None:
        raise RuntimeError("generation components require an opened DWARF session")
    lazy_index = _build_index(session, dwarf_info, options)
    type_resolver = _timed_component(
        "type_resolver", lambda: LazyTypeResolver(dwarf_info, lazy_index)
    )
    dump_parser = _build_dump_parser(options)
    class_parser = _timed_component(
        "class_parser",
        lambda: ClassParser(
            type_resolver,
            dwarf_info,
            lazy_index,
            exhaustive_search=options.exhaustive_search,
            dwarf_dump_path=options.dwarf_dump_path,
            dwarf_index_path=options.dwarf_index_path,
            query_port=session.query_port,
            resolve_param_names=options.resolve_param_names,
            dump_parser=dump_parser,
        ),
    )
    header_renderer = _timed_component(
        "header_renderer", lambda: HeaderRenderer(lazy_index, class_parser)
    )
    hierarchy_builder = _timed_component(
        "hierarchy_builder", lambda: HierarchyBuilder(class_parser, lazy_index)
    )
    return GenerationRuntime(
        elf_path=options.elf_path,
        dwarf_info=dwarf_info,
        platform=session.platform,
        lazy_index=lazy_index,
        type_resolver=type_resolver,
        class_parser=class_parser,
        header_renderer=header_renderer,
        hierarchy_builder=hierarchy_builder,
        dump_lookup_factory=options.dump_lookup_factory,
        disassembly_factory=options.disassembly_factory,
        source_hash=options.source_hash,
        source_identity=options.source_identity,
    )


def _build_index(
    session: DwarfSession,
    dwarf_info: DwarfInfo,
    options: GenerationComponentOptions,
) -> DwarfLookupPort:
    provided_index = session.query_index
    if provided_index is not None:
        return provided_index
    from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService

    return _timed_component(
        "lazy_index",
        lambda: LazyDwarfIndexService(
            dwarf_info,
            str(options.cache_file or Path(".dwarf_cache.json")),
            die_cache_size=options.die_cache_size,
            type_cache_size=options.type_cache_size,
            search_timeout=options.search_timeout,
            source_file_path=options.elf_path,
            source_identity=options.source_identity,
        ),
    )


def _build_dump_parser(options: GenerationComponentOptions):
    if options.dump_lookup_factory is None or options.dwarf_dump_path is None:
        return None
    return options.dump_lookup_factory(options.dwarf_dump_path, options.dwarf_index_path)


def _timed_component(name: str, factory):
    started_at = perf_counter()
    component = factory()
    log_event(
        logger,
        logging.DEBUG,
        "generation_component_initialized",
        component=name,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )
    return component

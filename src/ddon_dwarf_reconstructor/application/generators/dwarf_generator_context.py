"""Typed collaboration contract for the application generator mixins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...core.dwarf import DwarfInfo
from ...core.platform import ELFPlatform
from ...domain.ports.class_parser import ClassParserPort
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.dwarf_lookup import DwarfLookupPort
from ...domain.ports.source_identity import SourceHashPort, SourceIdentityPort
from ...domain.ports.type_resolution import TypeResolverPort
from ...domain.ports.validation_dump import ValidationDumpFactory
from ...domain.services.generation import HeaderGenerator, HierarchyBuilder

if TYPE_CHECKING:
    from .generator_workflow import GeneratorWorkflow


class DwarfGeneratorContext(Protocol):
    """State and operations shared by the generator responsibilities."""

    elf_path: Path
    platform: ELFPlatform
    dwarf_info: DwarfInfo | None
    class_parser: ClassParserPort | None
    type_resolver: TypeResolverPort | None
    header_generator: HeaderGenerator | None
    lazy_index: DwarfLookupPort | None
    hierarchy_builder: HierarchyBuilder | None
    dump_lookup_factory: ValidationDumpFactory | None
    disassembly_factory: DisassemblyProducerFactory | None
    source_hash: SourceHashPort | None
    source_identity: SourceIdentityPort | None
    workflow: GeneratorWorkflow

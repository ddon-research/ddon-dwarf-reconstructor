"""Composition-root factories for infrastructure adapters."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ..domain.ports.disassembly import DisassemblyProducerPort
from ..domain.ports.dump_lookup import DumpLookupPort
from .elf_session import ElfDwarfSession
from .orbis_objdump import OrbisObjdumpProducer
from .zstd_dump_parser import ZstdDumpParser


def create_dwarf_session(elf_path: Path) -> ElfDwarfSession:
    """Build the concrete ELF/DWARF lifecycle adapter for the application."""
    return ElfDwarfSession(elf_path)


def create_dump_lookup(path: Path, index_path: Path | None) -> DumpLookupPort:
    """Build the compressed-DWARF adapter for an application port."""
    return cast(DumpLookupPort, ZstdDumpParser(path, index_path))


def create_disassembly_producer(executable: Path) -> DisassemblyProducerPort:
    """Build the Orbis objdump adapter for an application port."""
    return OrbisObjdumpProducer(executable)

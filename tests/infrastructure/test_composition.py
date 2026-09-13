"""Composition-root tests for concrete infrastructure adapter wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.composition import (
    create_disassembly_factory,
    create_disassembly_producer,
    create_dump_lookup,
    create_dwarf_session,
)
from ddon_dwarf_reconstructor.infrastructure.elf_session import ElfDwarfSession
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import OrbisObjdumpProducer
from ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser import ZstdDumpParser


@pytest.mark.unit
@pytest.mark.functional
def test_composition_builds_concrete_lifecycle_adapters_without_application_imports(
    tmp_path: Path,
) -> None:
    dump_path = tmp_path / "dump.zst"
    dump_path.write_bytes(b"")

    assert isinstance(create_dwarf_session(Path("input.elf")), ElfDwarfSession)
    assert isinstance(create_dump_lookup(dump_path, None), ZstdDumpParser)
    assert isinstance(create_disassembly_producer(Path("input.elf")), OrbisObjdumpProducer)


@pytest.mark.unit
@pytest.mark.functional
def test_default_disassembly_factory_preserves_direct_constructor_identity() -> None:
    factory = create_disassembly_factory()

    assert factory is create_disassembly_producer


@pytest.mark.unit
@pytest.mark.functional
def test_disassembly_factory_captures_only_explicit_cross_check_options() -> None:
    factory = create_disassembly_factory(
        llvm_readobj_path=Path("readobj.exe"),
        llvm_objdump_path=Path("objdump.exe"),
        llvm_target_triple="x86_64-test",
    )

    producer = factory(Path("input.elf"))
    assert isinstance(producer, OrbisObjdumpProducer)
    assert producer.llvm_readobj_path == Path("readobj.exe").resolve()
    assert producer.llvm_objdump_path == Path("objdump.exe").resolve()
    assert producer.llvm_target_triple == "x86_64-test"

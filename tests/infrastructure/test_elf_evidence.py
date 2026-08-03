from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure.elf_evidence import inspect_open_elf


def _cu(version: int, offset: int, producer: bytes, language: int) -> Mock:
    top_die = Mock()
    top_die.attributes = {
        "DW_AT_producer": Mock(value=producer),
        "DW_AT_language": Mock(value=language),
    }
    unit = Mock(cu_offset=offset)
    unit.header = {"version": version}
    unit.get_top_DIE.return_value = top_die
    return unit


@pytest.mark.unit
@pytest.mark.regression
def test_elf_evidence_summarizes_all_cu_headers_and_producers() -> None:
    elf = Mock()
    elf.header = {
        "e_machine": "EM_X86_64",
        "e_type": "ET_EXEC",
        "e_ident": {"EI_OSABI": "ELFOSABI_FREEBSD"},
    }
    elf.elfclass = 64
    elf.little_endian = True
    section = Mock()
    section.name = ".debug_info"
    other_section = Mock()
    other_section.name = ".text"
    elf.iter_sections.return_value = [section, other_section]
    dwarf = Mock()
    dwarf.iter_CUs.return_value = [
        _cu(4, 0x10, b"clang ps4", 4),
        _cu(4, 0x20, b"clang ps4", 12),
    ]
    elf.has_dwarf_info.return_value = True
    elf.get_dwarf_info.return_value = dwarf

    evidence = inspect_open_elf(elf, "fixture.elf")

    assert evidence["platform"] == "ps4"
    assert evidence["elf"] == {
        "class": "64",
        "machine": "EM_X86_64",
        "type": "ET_EXEC",
        "osabi": "ELFOSABI_FREEBSD",
        "endianness": "little",
    }
    assert evidence["dwarf"]["cu_count"] == 2
    assert evidence["dwarf"]["versions"] == {"4": 2}
    assert evidence["dwarf"]["producers"] == {"clang ps4": 2}
    assert evidence["dwarf"]["languages"] == {"12": 1, "4": 1}
    assert evidence["dwarf"]["debug_sections"] == [".debug_info"]


@pytest.mark.unit
def test_elf_evidence_handles_elf_without_dwarf() -> None:
    elf = Mock()
    elf.header = {
        "e_machine": "EM_X86_64",
        "e_type": "ET_EXEC",
        "e_ident": {"EI_OSABI": "ELFOSABI_NONE"},
    }
    elf.elfclass = 64
    elf.little_endian = True
    elf.iter_sections.return_value = []
    elf.has_dwarf_info.return_value = False

    evidence = inspect_open_elf(elf)

    assert evidence["dwarf"]["cu_count"] == 0
    assert evidence["dwarf"]["versions"] == {}
    assert evidence["dwarf"]["producers"] == {}

"""Tests for source-provenance-bound PS4/Orbis definitions."""

import pytest

from ddon_dwarf_reconstructor.infrastructure.orbis_sdk_definitions import (
    DEFAULT_PS4_LLVM_TRIPLE,
    ELF_MACHINE_X86_64,
    ELFOSABI_FREEBSD,
    ORBIS_BFD_TARGET,
    ORBIS_COMMON_PAGE_SIZE,
    ORBIS_MIN_PAGE_SIZE,
    ORBIS_RELOCATION_DEFINITIONS,
    PT_GNU_RELRO,
    PT_SCE_DYNLIBDATA,
    PT_SCE_PROCPARAM,
    SCE_DYNAMIC_TAG_NAMES,
    SCE_PROGRAM_HEADER_NAMES,
    SDK_DEFINITION_SOURCE,
    SDK_DEFINITION_VERSION,
    sdk_definition_identity,
)


@pytest.mark.unit
@pytest.mark.functional
def test_sdk_definitions_preserve_official_program_headers_and_target_facts() -> None:
    assert SCE_PROGRAM_HEADER_NAMES == {
        0x61000000: "PT_SCE_DYNLIBDATA",
        0x61000001: "PT_SCE_PROCPARAM",
        0x6FFFFF00: "PT_SCE_COMMENT",
        0x6FFFFF01: "PT_SCE_LIBVERSION",
    }
    assert PT_SCE_DYNLIBDATA == 0x61000000
    assert PT_SCE_PROCPARAM == 0x61000001
    assert PT_GNU_RELRO == 0x6474E552
    assert DEFAULT_PS4_LLVM_TRIPLE == "x86_64-scei-ps4"
    assert ORBIS_BFD_TARGET == "elf64-x86-64-freebsd"
    assert ELF_MACHINE_X86_64 == 0x3E
    assert ELFOSABI_FREEBSD == 9
    assert ORBIS_MIN_PAGE_SIZE == ORBIS_COMMON_PAGE_SIZE == 0x4000


@pytest.mark.unit
@pytest.mark.functional
def test_sdk_dynamic_tags_and_custom_relocation_are_complete_and_typed() -> None:
    assert set(SCE_DYNAMIC_TAG_NAMES) == {
        0x61000005,
        0x61000007,
        0x61000009,
        0x6100000D,
        0x6100000F,
        0x61000011,
        0x61000013,
        0x61000015,
        0x61000017,
        0x61000019,
        0x6100001D,
        0x6100001F,
        0x61000021,
        0x61000023,
        0x61000025,
        0x61000027,
        0x61000029,
        0x6100002B,
        0x6100002D,
        0x6100002F,
        0x61000031,
        0x61000033,
        0x61000035,
        0x61000037,
        0x61000039,
        0x6100003B,
        0x6100003D,
        0x6100003F,
    }
    relocation = ORBIS_RELOCATION_DEFINITIONS[0x28]
    assert relocation.name == "R_X86_64_ORBIS_GOTPCREL_LOAD"
    assert relocation.size_bytes == 4
    assert relocation.bitsize == 32
    assert relocation.pc_relative is True
    assert relocation.overflow == "signed"


@pytest.mark.unit
@pytest.mark.functional
def test_sdk_definition_identity_retains_source_hashes_and_no_sce_relro() -> None:
    identity = sdk_definition_identity()

    assert identity["version"] == SDK_DEFINITION_VERSION
    assert identity["target_triple"] == DEFAULT_PS4_LLVM_TRIPLE
    assert "source" in identity
    assert len(SDK_DEFINITION_SOURCE.files) == 4
    assert all(len(sha256) == 64 for _, sha256, _ in SDK_DEFINITION_SOURCE.files)
    assert "PT_SCE_RELRO" not in SCE_PROGRAM_HEADER_NAMES.values()

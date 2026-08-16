"""Typed Sony/Orbis ELF definitions reproduced from the SDK source package.

The runtime does not import or execute the SDK source.  These values are the
small, reviewed subset needed to describe PS4 program headers, dynamic tags,
and relocation evidence.  Unknown values remain numeric at the parser boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..domain.models.disassembly import OrbisDefinitionSource, OrbisSdkDefinitionIdentity

SDK_DEFINITION_VERSION = "orbis-sdk6500-n267"
# Compatibility spelling used by the profile/cache layer.
SDK_DEFINITIONS_VERSION = SDK_DEFINITION_VERSION
SDK_PACKAGE_LABEL = "binutils-orbis-2_22_1-src-SDK6500-n267"
SDK_SOURCE_ROOT = "ORBIS SDK 8.000/license/src_package"

DEFAULT_PS4_LLVM_TRIPLE = "x86_64-scei-ps4"
ORBIS_CONFIGURE_TRIPLE = "x86_64-orbis-freebsd9"
ORBIS_BFD_TARGET = "elf64-x86-64-freebsd"
ELF_MACHINE_X86_64 = 0x3E
ELFOSABI_FREEBSD = 9
ORBIS_MIN_PAGE_SIZE = 0x4000
ORBIS_COMMON_PAGE_SIZE = 0x4000
PT_GNU_RELRO = 0x6474E552

PT_SCE_DYNLIBDATA = 0x61000000
PT_SCE_PROCPARAM = 0x61000001
PT_SCE_COMMENT = 0x6FFFFF00
PT_SCE_LIBVERSION = 0x6FFFFF01

SCE_PROGRAM_HEADER_NAMES = {
    PT_SCE_DYNLIBDATA: "PT_SCE_DYNLIBDATA",
    PT_SCE_PROCPARAM: "PT_SCE_PROCPARAM",
    PT_SCE_COMMENT: "PT_SCE_COMMENT",
    PT_SCE_LIBVERSION: "PT_SCE_LIBVERSION",
}

# The values and names below are reproduced from include/elf/common.h in the
# SDK package.  Some tags are only named by binutils; their payload semantics
# intentionally remain opaque in the parser.
SCE_DYNAMIC_TAG_NAMES = {
    0x61000005: "DT_SCE_IDTABENTSZ",
    0x61000007: "DT_SCE_FINGERPRINT",
    0x61000009: "DT_SCE_ORIGINAL_FILENAME",
    0x6100000D: "DT_SCE_MODULE_INFO",
    0x6100000F: "DT_SCE_NEEDED_MODULE",
    0x61000011: "DT_SCE_MODULE_ATTR",
    0x61000013: "DT_SCE_EXPORT_LIB",
    0x61000015: "DT_SCE_IMPORT_LIB",
    0x61000017: "DT_SCE_EXPORT_LIB_ATTR",
    0x61000019: "DT_SCE_IMPORT_LIB_ATTR",
    0x6100001D: "DT_SCE_STUB_MODULE_NAME",
    0x6100001F: "DT_SCE_STUB_MODULE_VERSION",
    0x61000021: "DT_SCE_STUB_LIBRARY_NAME",
    0x61000023: "DT_SCE_STUB_LIBRARY_VERSION",
    0x61000025: "DT_SCE_HASH",
    0x61000027: "DT_SCE_PLTGOT",
    0x61000029: "DT_SCE_JMPREL",
    0x6100002B: "DT_SCE_PLTREL",
    0x6100002D: "DT_SCE_PLTRELSZ",
    0x6100002F: "DT_SCE_RELA",
    0x61000031: "DT_SCE_RELASZ",
    0x61000033: "DT_SCE_RELAENT",
    0x61000035: "DT_SCE_STRTAB",
    0x61000037: "DT_SCE_STRSZ",
    0x61000039: "DT_SCE_SYMTAB",
    0x6100003B: "DT_SCE_SYMENT",
    0x6100003D: "DT_SCE_HASHSZ",
    0x6100003F: "DT_SCE_SYMTABSZ",
}

RELA_ENTRY_SIZE = 24


@dataclass(frozen=True, slots=True)
class OrbisRelocationDefinition:
    """Verified BFD properties for one Orbis relocation code."""

    code: int
    name: str
    size_bytes: int
    bitsize: int
    pc_relative: bool
    overflow: str
    linker_behavior: str


ORBIS_RELOCATION_DEFINITIONS = {
    0x28: OrbisRelocationDefinition(
        code=0x28,
        name="R_X86_64_ORBIS_GOTPCREL_LOAD",
        size_bytes=4,
        bitsize=32,
        pc_relative=True,
        overflow="signed",
        linker_behavior=(
            "Compiler-generated optimized GOT load; the SN linker patches the instruction "
            "and gold treats it like R_X86_64_GOTPCREL."
        ),
    )
}

# Common relocation names observed in the ELF and retained for readable
# evidence.  Unlisted values remain numeric and are never guessed.
RELOCATION_NAMES = {
    0: "R_X86_64_NONE",
    1: "R_X86_64_64",
    2: "R_X86_64_PC32",
    3: "R_X86_64_GOT32",
    4: "R_X86_64_PLT32",
    5: "R_X86_64_COPY",
    6: "R_X86_64_GLOB_DAT",
    7: "R_X86_64_JUMP_SLOT",
    8: "R_X86_64_RELATIVE",
    9: "R_X86_64_GOTPCREL",
    10: "R_X86_64_32",
    11: "R_X86_64_32S",
    12: "R_X86_64_16",
    13: "R_X86_64_PC16",
    14: "R_X86_64_8",
    15: "R_X86_64_PC8",
    16: "R_X86_64_DTPMOD64",
    17: "R_X86_64_DTPOFF64",
    18: "R_X86_64_TPOFF64",
    19: "R_X86_64_TLSGD",
    20: "R_X86_64_TLSLD",
    21: "R_X86_64_DTPOFF32",
    22: "R_X86_64_GOTTPOFF",
    23: "R_X86_64_TPOFF32",
    24: "R_X86_64_PC64",
    25: "R_X86_64_GOTOFF64",
    26: "R_X86_64_GOTPC32",
    27: "R_X86_64_GOT64",
    28: "R_X86_64_GOTPCREL64",
    29: "R_X86_64_GOTPC64",
    30: "R_X86_64_GOTPLT64",
    31: "R_X86_64_PLTOFF64",
    34: "R_X86_64_GOTPC32_TLSDESC",
    35: "R_X86_64_TLSDESC_CALL",
    36: "R_X86_64_TLSDESC",
    37: "R_X86_64_IRELATIVE",
    38: "R_X86_64_RELATIVE64",
    **{code: definition.name for code, definition in ORBIS_RELOCATION_DEFINITIONS.items()},
}


@dataclass(frozen=True, slots=True)
class SdkDefinitionSource:
    """Source identity for the reproduced SDK definitions."""

    package: str
    root: str
    files: tuple[tuple[str, str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SDK_DEFINITION_SOURCE = SdkDefinitionSource(
    package=SDK_PACKAGE_LABEL,
    root=SDK_SOURCE_ROOT,
    files=(
        (
            "binutils/include/elf/common.h",
            "fd1e5ae5387ce79af05d37eba41cc03004ef24905b4536787d4a8bca5d994604",
            40438,
        ),
        (
            "binutils/include/elf/x86-64.h",
            "916812323a2d22b7de7fe6c171d73e0ac6e44c255e33cc7b3c56f1aa57bf3279",
            5129,
        ),
        (
            "binutils/bfd/elf64-x86-64.c",
            "d3ea74fa5c6ab07a495ec1037197c41756256fcda3ac921b10206fa12026c1ca",
            150962,
        ),
        (
            "binutils/README-ORBIS",
            "0e7a30e37a452b1910b7b1431aaf603f39da47bbbb7298724e5d55a0ce56f818",
            1425,
        ),
    ),
)


def sdk_definition_identity() -> dict[str, object]:
    """Return deterministic identity material for cache keys and reports."""
    return {
        "version": SDK_DEFINITION_VERSION,
        "source": SDK_DEFINITION_SOURCE.to_dict(),
        "target_triple": DEFAULT_PS4_LLVM_TRIPLE,
        "bfd_target": ORBIS_BFD_TARGET,
    }


def sdk_definition_model() -> OrbisSdkDefinitionIdentity:
    """Return the typed report identity for the reproduced definition subset."""
    return OrbisSdkDefinitionIdentity(
        version=SDK_DEFINITION_VERSION,
        target_triple=DEFAULT_PS4_LLVM_TRIPLE,
        bfd_target=ORBIS_BFD_TARGET,
        source=OrbisDefinitionSource(
            package=SDK_DEFINITION_SOURCE.package,
            root=SDK_DEFINITION_SOURCE.root,
            files=SDK_DEFINITION_SOURCE.files,
        ),
    )


__all__ = [
    "DEFAULT_PS4_LLVM_TRIPLE",
    "ELF_MACHINE_X86_64",
    "ELFOSABI_FREEBSD",
    "ORBIS_COMMON_PAGE_SIZE",
    "ORBIS_MIN_PAGE_SIZE",
    "ORBIS_RELOCATION_DEFINITIONS",
    "ORBIS_BFD_TARGET",
    "ORBIS_CONFIGURE_TRIPLE",
    "PT_GNU_RELRO",
    "PT_SCE_COMMENT",
    "PT_SCE_DYNLIBDATA",
    "PT_SCE_LIBVERSION",
    "PT_SCE_PROCPARAM",
    "RELA_ENTRY_SIZE",
    "RELOCATION_NAMES",
    "SCE_DYNAMIC_TAG_NAMES",
    "SCE_PROGRAM_HEADER_NAMES",
    "SDK_DEFINITION_SOURCE",
    "SDK_DEFINITIONS_VERSION",
    "SDK_DEFINITION_VERSION",
    "sdk_definition_identity",
    "sdk_definition_model",
]

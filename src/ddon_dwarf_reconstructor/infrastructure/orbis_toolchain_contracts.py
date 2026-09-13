"""Reviewed Orbis SDK toolchain contracts and profile selection."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..domain.models.orbis_toolchain import OrbisToolchainContract

SDK12_ROOT = Path(r"D:\SCE\ORBIS SDKs\12.000")
SDK8_ROOT = Path(r"D:\SCE\ORBIS SDKs\8.000")
SDK12_PROFILE_ID = "orbis-sdk12-llvm18"
SDK8_PROFILE_ID = "orbis-sdk8-llvm10"

_DOCUMENTATION_SOURCES = (
    r"D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Assembler-Guidelines",
    r"D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Compiler_ABI-Overview",
    r"D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Generating_and_Using_Dynamic_Libraries\Sysmodule-Reference\ps4-module-ids.html",
    r"D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Analysis_and_Debugging\Machine_Code_Analyzer-Overview\analyzing-assembly-code-generated-by-the-compiler.html",
)

_COMMON_COMPILER_DEFAULTS = (
    "target=x86_64-scei-ps4",
    "relocation-model=pic",
    "pic-level=2",
    "small-pic-code-model",
    "function-sections=enabled",
    "data-sections=enabled",
    "dwarf2-cfi-asm=enabled",
    "dwarf-aranges=enabled",
    "frame-pointer=non-leaf",
    "visibility=hidden",
    "exceptions=disabled",
    "rtti=disabled",
    "sce-stack-sizes=enabled",
)

_COMMON_ABI_RULES = (
    "gp-arguments=rdi,rsi,rdx,rcx,r8,r9",
    "sse-arguments=xmm0-xmm7",
    "register-classes=integer,sse,x87,memory",
    "memory-return=hidden-rdi-and-rax",
    "stack-alignment=16-or-32-for-stack-m256",
    "red-zone=128",
    "varargs-vector-count=rax-low-byte",
    "varargs-m256=stack",
    "enum-char=underlying-type-and-width",
    "tls=fs-segment-relative",
    "pic-hand-assembly=rip-relative",
    "sysmodule-ids=not-nid-module-identities",
)

SDK12_CONTRACT = OrbisToolchainContract(
    profile_id=SDK12_PROFILE_ID,
    sdk_version="12.000",
    clang_version="LLVM 18.1.6 / PS4 clang 12.00.0.543",
    assembler_version="GNU Binutils 2.22 Orbis12.00.0.540",
    linker_version="orbis-ld 12.00.0.2",
    llvm_mca_version="LLVM 18.1.6",
    target_triple="x86_64-scei-ps4",
    bfd_target="elf64-x86-64-freebsd",
    configure_triple="x86_64-orbis-freebsd9",
    assembler_syntax="att",
    integrated_assembler_default=True,
    compiler_defaults=_COMMON_COMPILER_DEFAULTS,
    abi_rules=(*_COMMON_ABI_RULES, "int128=single-register-shortage-spills-whole-argument"),
    elf_rules=("stack-metadata=.sce_stack_sizes",),
    elf_flags=("EF_FFUNC_DATA_SECS_ENABLED=0x04000000",),
    relocation_definitions=("R_X86_64_ORBIS_GOTPCREL_LOAD=0x28",),
    documentation_sources=_DOCUMENTATION_SOURCES,
)

SDK8_CONTRACT = OrbisToolchainContract(
    profile_id=SDK8_PROFILE_ID,
    sdk_version="8.000",
    clang_version="LLVM 10 / PS4 clang 8.00.0.403",
    assembler_version="GNU Binutils 2.22 Orbis8.00.0.398",
    linker_version="orbis-ld 8.00.0.514",
    llvm_mca_version="LLVM 10",
    target_triple="x86_64-scei-ps4",
    bfd_target="elf64-x86-64-freebsd",
    configure_triple="x86_64-orbis-freebsd9",
    assembler_syntax="att",
    integrated_assembler_default=True,
    compiler_defaults=_COMMON_COMPILER_DEFAULTS,
    abi_rules=(*_COMMON_ABI_RULES, "int128=legacy-ps4-register-stack-edge-case"),
    elf_rules=("stack-metadata=.sce_stack_sizes",),
    elf_flags=("EF_FFUNC_DATA_SECS_ENABLED=0x04000000",),
    relocation_definitions=("R_X86_64_ORBIS_GOTPCREL_LOAD=0x28",),
    documentation_sources=_DOCUMENTATION_SOURCES,
)

CONTRACTS = {
    SDK12_PROFILE_ID: SDK12_CONTRACT,
    SDK8_PROFILE_ID: SDK8_CONTRACT,
}


def get_toolchain_contract(profile_id: str) -> OrbisToolchainContract:
    """Return a reviewed contract by stable profile identifier."""
    try:
        return CONTRACTS[profile_id]
    except KeyError as error:
        available = ", ".join(sorted(CONTRACTS))
        raise ValueError(
            f"Unknown Orbis toolchain profile {profile_id!r}; choose from {available}"
        ) from error


def profile_id_for_path(path: Path) -> str | None:
    """Infer an SDK profile only from an explicit SDK path component."""
    parts = {part.casefold() for part in path.resolve().parts}
    if "12.000" in parts:
        return SDK12_PROFILE_ID
    if "8.000" in parts:
        return SDK8_PROFILE_ID
    return None


def select_toolchain_profile(
    sdk_root: Path | None,
    tool_paths: Iterable[Path] = (),
) -> tuple[str, tuple[str, ...]]:
    """Select one profile and reject explicitly mixed SDK families."""
    candidates = [profile_id_for_path(sdk_root)] if sdk_root is not None else []
    candidates.extend(profile_id_for_path(path) for path in tool_paths)
    selected = {item for item in candidates if item is not None}
    if len(selected) > 1:
        names = ", ".join(sorted(selected))
        raise ValueError(f"Mixed Orbis SDK toolchain profiles are not allowed: {names}")
    if selected:
        return next(iter(selected)), ()
    return SDK12_PROFILE_ID, ("toolchain profile inferred from promoted SDK12 default",)


__all__ = [
    "CONTRACTS",
    "SDK8_CONTRACT",
    "SDK8_PROFILE_ID",
    "SDK8_ROOT",
    "SDK12_CONTRACT",
    "SDK12_PROFILE_ID",
    "SDK12_ROOT",
    "get_toolchain_contract",
    "profile_id_for_path",
    "select_toolchain_profile",
]

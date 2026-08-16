"""Versioned Orbis and LLVM evidence profile definitions."""

from .orbis_sdk_definitions import DEFAULT_PS4_LLVM_TRIPLE, SDK_DEFINITION_VERSION

REPORT_SCHEMA_VERSION = "2.4"
PARSER_VERSION = "orbis-objdump-text-v7"
SCE_METADATA_PARSER_VERSION = "orbis-sce-metadata-v3"
SDK_DEFINITIONS_VERSION = SDK_DEFINITION_VERSION
DISASSEMBLY_FLAGS = (
    "-EL",
    "-d",
    "-l",
    "-F",
    "-C",
    "-w",
    "--prefix-addresses",
    "--show-raw-insn",
)
SYMBOL_FALLBACK_FLAGS = ("-t", "-C", "-w", "--special-syms")
# The PS4 SDK accepts the plain symbol-table request but rejects the historical
# ``-t -T`` combination with ``Invalid operation``.  Keep one authoritative
# symbol request so normal generation never performs a known-failing retry.
SYMBOL_FLAGS = SYMBOL_FALLBACK_FLAGS
PRIVATE_HEADERS_FLAGS = ("-p", "-C", "-w", "-F")
STANDARD_RELOCATION_FLAGS = ("-r", "-C", "-w", "-F")
# ``-R`` is rejected by the PS4 SDK 8.0 objdump.  SCE dynamic relocation data
# is read by OrbisSceMetadataReader; there is deliberately no SDK invocation
# for this unsupported profile.
DYNAMIC_RELOCATION_FLAGS = ()
LLVM_METADATA_FLAGS = (
    "--elf-output-style=JSON",
    "--file-header",
    "--program-headers",
    "--sections",
    "--dynamic-table",
    "--relocations",
    "--dyn-relocations",
)
LLVM_TARGET_DISASSEMBLY_FLAGS = (
    "-d",
    "-l",
    "-C",
    "--symbolize-operands",
)
LLVM_TARGET_CAPABILITY_FLAGS = (
    "--triple",
    *LLVM_TARGET_DISASSEMBLY_FLAGS,
    "--start-address",
    "--stop-address",
)
LLVM_TARGET_PROFILE = "llvm-ps4-disassembly"
LLVM_TARGET_TRIPLE = DEFAULT_PS4_LLVM_TRIPLE
SOURCE_INTERMIXED_FLAGS = (*DISASSEMBLY_FLAGS, "-S")
DEBUG_FLAGS = ("-g",)
DEFAULT_DWARF_MODES = (
    "rawline",
    "decodedline",
    "info",
    "abbrev",
    "pubnames",
    "aranges",
    "macro",
    "frames",
    "frames-interp",
    "str",
    "loc",
    "Ranges",
    "pubtypes",
)

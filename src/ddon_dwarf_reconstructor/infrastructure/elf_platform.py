#!/usr/bin/env python3

"""ELF platform detection and classification.

Detects the target platform of an ELF file (PS3, PS4, PC, etc.) based on:
- Machine architecture (e.g., x86-64, PowerPC64)
- Endianness (little-endian vs big-endian)
- DWARF version in debug info
- OS/ABI field
"""

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..core.observability import get_logger
from ..core.platform import ELFPlatform

logger = get_logger(__name__)


class PlatformDetector:
    """Detects the target platform of an ELF file."""

    # Machine type strings (as returned by pyelftools)
    MACHINE_POWERPC64_STR = "EM_PPC64"
    MACHINE_X86_64_STR = "EM_X86_64"

    # Machine types from ELF specification (numeric)
    MACHINE_POWERPC64 = 0x15  # PowerPC 64-bit
    MACHINE_X86_64 = 0x3E  # x86-64

    # OS/ABI types from ELF specification
    OSABI_NONE = 0x00  # Unix System V ABI
    OSABI_LINUX = 0x03  # Linux
    OSABI_FREEBSD = 0x09  # FreeBSD

    @staticmethod
    def detect(elf_path: str) -> ELFPlatform:
        """Detect platform from ELF file.

        Args:
            elf_path: Path to the ELF file

        Returns:
            Detected platform (PS3, PS4, or UNKNOWN)
        """
        try:
            with open(elf_path, "rb") as f:
                return PlatformDetector.detect_elf(ELFFile(f), elf_path)

        except (
            ELFError,
            OSError,
            AttributeError,
            KeyError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            logger.error("Failed to detect platform from %s: %s", elf_path, error)
            return ELFPlatform.UNKNOWN

    @staticmethod
    def detect_elf(elf: ELFFile, elf_path: str = "<open ELF>") -> ELFPlatform:
        """Classify an already-open ELF without reopening the source path."""
        try:
            machine_str = elf.header["e_machine"]
            is_little_endian: bool = elf.little_endian
            dwarf_version = PlatformDetector._get_dwarf_version(elf)
            logger.debug(
                "ELF characteristics: machine=%s, little_endian=%s, dwarf_version=%s",
                machine_str,
                is_little_endian,
                dwarf_version,
            )
            if machine_str == PlatformDetector.MACHINE_POWERPC64_STR and not is_little_endian:
                logger.info("Detected PS3 ELF (PowerPC64 big-endian)")
                return ELFPlatform.PS3
            if machine_str == PlatformDetector.MACHINE_X86_64_STR and is_little_endian:
                logger.info("Detected PS4 ELF (x86-64 little-endian)")
                return ELFPlatform.PS4
            logger.warning(
                "Unknown platform: machine=%s (little_endian=%s)", machine_str, is_little_endian
            )
            return ELFPlatform.UNKNOWN
        except (
            ELFError,
            AttributeError,
            KeyError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            logger.error("Failed to classify ELF %s: %s", elf_path, error)
            return ELFPlatform.UNKNOWN

    @staticmethod
    def _get_dwarf_version(elf: ELFFile) -> int | None:
        """Extract DWARF version from ELF file if available.

        Args:
            elf: ELFFile object

        Returns:
            DWARF version (2, 3, 4, 5) or None if not found
        """
        try:
            if not elf.has_dwarf_info():
                return None

            dwarf_info = elf.get_dwarf_info()
            for cu in dwarf_info.iter_CUs():
                # DWARF version is in the compilation unit header
                version: int = cu.header["version"]
                return version

        except (ELFError, AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.debug("Unable to read DWARF version: %s", error)

        return None

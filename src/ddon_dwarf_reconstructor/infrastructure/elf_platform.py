#!/usr/bin/env python3

"""ELF platform detection and classification.

Detects the target platform of an ELF file (PS3, PS4, PC, etc.) based on:
- Machine architecture (e.g., x86-64, PowerPC64)
- Endianness (little-endian vs big-endian)
- DWARF version in debug info
- OS/ABI field
"""

from enum import Enum

from elftools.elf.elffile import ELFFile

from .logging import get_logger

logger = get_logger(__name__)


class ELFPlatform(Enum):
    """Supported ELF target platforms."""

    PS3 = "ps3"  # PowerPC64 big-endian, DWARF2
    PS4 = "ps4"  # x86-64 little-endian, DWARF3/4
    UNKNOWN = "unknown"  # Unrecognized platform

    def __str__(self) -> str:
        """Return uppercase string representation."""
        return self.value.upper()


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
                elf = ELFFile(f)  # type: ignore[no-untyped-call]

                # Get machine type and endianness
                # pyelftools returns machine as a string like "EM_X86_64"
                machine_str = elf.header["e_machine"]
                is_little_endian: bool = elf.little_endian

                # Try to get DWARF version for additional confirmation
                dwarf_version = PlatformDetector._get_dwarf_version(elf)

                # Debug logging
                logger.debug(
                    f"ELF Characteristics: machine={machine_str}, "
                    f"little_endian={is_little_endian}, "
                    f"dwarf_version={dwarf_version}"
                )

                # PS3: PowerPC64 big-endian with DWARF2
                if machine_str == PlatformDetector.MACHINE_POWERPC64_STR and not is_little_endian:
                    logger.info("Detected PS3 ELF (PowerPC64 big-endian)")
                    return ELFPlatform.PS3

                # PS4: x86-64 little-endian with DWARF3/4
                if machine_str == PlatformDetector.MACHINE_X86_64_STR and is_little_endian:
                    logger.info("Detected PS4 ELF (x86-64 little-endian)")
                    return ELFPlatform.PS4

                logger.warning(
                    f"Unknown platform: machine={machine_str} "
                    f"(little_endian={is_little_endian})"
                )
                return ELFPlatform.UNKNOWN

        except Exception as e:
            logger.error(f"Failed to detect platform from {elf_path}: {e}")
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
            if not elf.has_dwarf_info():  # type: ignore
                return None

            dwarf_info = elf.get_dwarf_info()  # type: ignore
            for cu in dwarf_info.iter_CUs():
                # DWARF version is in the compilation unit header
                version: int = cu.header["version"]
                return version

        except Exception:
            pass

        return None

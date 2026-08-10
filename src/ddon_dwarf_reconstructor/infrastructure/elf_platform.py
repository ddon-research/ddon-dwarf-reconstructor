#!/usr/bin/env python3

"""ELF platform detection and classification.

Detects the target platform of an ELF file (PS3, PS4, PC, etc.) based on:
- Machine architecture (e.g., x86-64, PowerPC64)
- Endianness (little-endian vs big-endian)
- OS/ABI field
"""

import logging

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..core.observability import get_logger, log_event
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
            log_event(
                logger,
                logging.ERROR,
                "elf_platform_detection_failed",
                elf_path=elf_path,
                exc_info=error,
            )
            return ELFPlatform.UNKNOWN

    @staticmethod
    def detect_elf(elf: ELFFile, elf_path: str = "<open ELF>") -> ELFPlatform:
        """Classify an already-open ELF without reopening the source path."""
        try:
            machine_str = elf.header["e_machine"]
            is_little_endian: bool = elf.little_endian
            log_event(
                logger,
                logging.DEBUG,
                "elf_characteristics",
                elf_path=elf_path,
                machine=machine_str,
                little_endian=is_little_endian,
            )
            if machine_str == PlatformDetector.MACHINE_POWERPC64_STR and not is_little_endian:
                log_event(
                    logger, logging.INFO, "elf_platform_detected", elf_path=elf_path, platform="ps3"
                )
                return ELFPlatform.PS3
            if machine_str == PlatformDetector.MACHINE_X86_64_STR and is_little_endian:
                log_event(
                    logger, logging.INFO, "elf_platform_detected", elf_path=elf_path, platform="ps4"
                )
                return ELFPlatform.PS4
            log_event(
                logger,
                logging.WARNING,
                "elf_platform_unknown",
                elf_path=elf_path,
                machine=machine_str,
                little_endian=is_little_endian,
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
            log_event(
                logger,
                logging.ERROR,
                "elf_platform_classification_failed",
                elf_path=elf_path,
                exc_info=error,
            )
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
            log_event(
                logger,
                logging.DEBUG,
                "dwarf_version_unavailable",
                exc_info=error,
            )

        return None

#!/usr/bin/env python3

"""Base generator abstract class for DWARF processing.

This module provides the foundational abstract class for all DWARF generators,
establishing the interface and context management patterns.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.elf.elffile import ELFFile

from ..utils.elf_patches import patch_pyelftools_for_ps4
from ..utils.logger import get_logger

# Apply PS4 ELF patches globally
patch_pyelftools_for_ps4()

logger = get_logger(__name__)


class BaseGenerator(ABC):
    """Abstract base class for DWARF generators.

    Provides context management and ELF file handling for all generator implementations.
    Subclasses must implement the generate() method for their specific output format.
    """

    def __init__(self, elf_path: Path):
        """Initialize generator with ELF file path.

        Args:
            elf_path: Path to ELF file containing DWARF information

        Raises:
            ValueError: If ELF file doesn't exist or is invalid
        """
        self.elf_path = elf_path
        self.elf_file: ELFFile | None = None
        self.dwarf_info: DWARFInfo | None = None

    def __enter__(self) -> "BaseGenerator":
        """Context manager entry - opens ELF file and validates DWARF info.

        Returns:
            Self for context manager usage

        Raises:
            ValueError: If no DWARF information found in ELF file
        """
        logger.debug(f"Opening ELF file: {self.elf_path}")
        self.file_handle = open(self.elf_path, "rb")
        self.elf_file = ELFFile(self.file_handle)  # type: ignore[no-untyped-call]

        if not self.elf_file.has_dwarf_info():  # type: ignore[no-untyped-call]
            raise ValueError(f"No DWARF info found in {self.elf_path}")

        self.dwarf_info = self.elf_file.get_dwarf_info()  # type: ignore[no-untyped-call]
        logger.info(f"DWARF info loaded from {self.elf_path}")
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None
    ) -> None:
        """Context manager exit - closes ELF file handle."""
        if hasattr(self, "file_handle"):
            self.file_handle.close()
            logger.debug("ELF file closed")

    @abstractmethod
    def generate(self, symbol: str, **options: bool) -> str:
        """Generate output for the specified symbol.

        Args:
            symbol: Target symbol name to generate output for
            **options: Generator-specific options

        Returns:
            Generated output as string

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        pass

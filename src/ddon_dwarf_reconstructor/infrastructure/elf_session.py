"""Owned ELF and DWARF resources for one application generation session."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO

from elftools.elf.elffile import ELFFile

from ..core.dwarf import DwarfInfo
from ..core.observability import get_logger, log_event
from ..core.platform import ELFPlatform
from ..utils.elf_patches import patch_pyelftools_for_ps4
from .elf_platform import PlatformDetector

logger = get_logger(__name__)


class ElfDwarfSession:
    """Open, validate, and close one ELF/DWARF resource graph."""

    def __init__(self, elf_path: Path) -> None:
        self.elf_path = elf_path
        self.file_handle: BinaryIO | None = None
        self.elf_file: ELFFile | None = None
        self.dwarf_info: DwarfInfo | None = None
        self.platform = ELFPlatform.UNKNOWN

    def __enter__(self) -> ElfDwarfSession:
        patch_pyelftools_for_ps4()
        try:
            log_event(logger, logging.DEBUG, "elf_open_started", elf_path=self.elf_path)
            self.file_handle = open(self.elf_path, "rb")
            self.elf_file = ELFFile(self.file_handle)
            self.platform = PlatformDetector.detect_elf(self.elf_file, str(self.elf_path))
            if not self.elf_file.has_dwarf_info():
                raise ValueError(f"No DWARF info found in {self.elf_path}")
            self.dwarf_info = self.elf_file.get_dwarf_info()
            log_event(
                logger,
                logging.INFO,
                "elf_dwarf_loaded",
                elf_path=self.elf_path,
                platform=self.platform.value,
            )
            return self
        except Exception as error:
            log_event(
                logger,
                logging.ERROR,
                "elf_open_failed",
                elf_path=self.elf_path,
                exc_info=error,
            )
            self.close()
            raise
        except BaseException:
            self.close()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.close()

    def close(self) -> None:
        """Close the source handle and clear derived resource references."""
        if self.file_handle is not None:
            self.file_handle.close()
            self.file_handle = None
            log_event(logger, logging.DEBUG, "elf_closed", elf_path=self.elf_path)
        self.elf_file = None
        self.dwarf_info = None

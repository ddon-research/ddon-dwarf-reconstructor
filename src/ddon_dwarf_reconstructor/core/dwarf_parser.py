"""DWARF information parser for ELF files."""

import sys
from pathlib import Path
from typing import Optional, Generator

from elftools.dwarf.die import DIE as ElfDIE
from elftools.elf.elffile import ELFFile

from ..utils.elf_patches import patch_pyelftools_for_ps4
from .models import CompilationUnit, DIE, DIEReference, DWARFAttribute

# Apply PS4 ELF patches on module load
patch_pyelftools_for_ps4()


class DWARFParser:
    """Parser for extracting DWARF debug information from ELF files."""

    def __init__(self, elf_path: Path, verbose: bool = False) -> None:
        """
        Initialize the DWARF parser.

        Args:
            elf_path: Path to the ELF file
            verbose: Enable verbose output
        """
        self.elf_path = elf_path
        self.verbose = verbose
        self.elf_file: Optional[ELFFile] = None
        self.dwarf_info: Optional[any] = None

    def open(self) -> None:
        """Open and validate the ELF file."""
        if not self.elf_path.exists():
            raise FileNotFoundError(f"ELF file not found: {self.elf_path}")

        if not self.elf_path.is_file():
            raise ValueError(f"Not a file: {self.elf_path}")

        try:
            # Open file handle (keep it open for the lifetime of the parser)
            self.file_handle = open(self.elf_path, "rb")
            self.elf_file = ELFFile(self.file_handle, stream_loader=None)

            if self.verbose:
                print(f"Opened ELF file: {self.elf_path}")
                print(f"Architecture: {self.elf_file.get_machine_arch()}")

        except Exception as e:
            if hasattr(self, "file_handle"):
                self.file_handle.close()
            raise RuntimeError(f"Failed to open ELF file: {e}") from e

    def load_dwarf_info(self) -> None:
        """Load DWARF debug information from the ELF file."""
        if not self.elf_file:
            raise RuntimeError("ELF file not opened. Call open() first.")

        try:
            # PS4 ELF files may have non-standard sections that cause issues
            # Try to get DWARF info directly without checking has_dwarf_info()
            try:
                self.dwarf_info = self.elf_file.get_dwarf_info()
            except Exception as dwarf_err:
                # If direct access fails, try to check if DWARF sections exist
                if self.verbose:
                    print(f"Direct DWARF access failed: {dwarf_err}")
                    print("Attempting alternative DWARF section detection...")

                # Try to find debug sections manually
                has_debug_section = False
                try:
                    for section in self.elf_file.iter_sections():
                        if section.name.startswith('.debug_'):
                            has_debug_section = True
                            break
                except Exception:
                    pass

                if not has_debug_section:
                    raise ValueError(
                        f"No DWARF debug information found in {self.elf_path}. "
                        "This PS4 ELF file may not contain debug symbols."
                    )

                # If we found debug sections but can't load them, re-raise
                raise ValueError(
                    f"DWARF sections found but cannot be loaded due to PS4-specific "
                    f"ELF format issues: {dwarf_err}"
                ) from dwarf_err

            if not self.dwarf_info:
                raise ValueError(
                    f"No DWARF debug information found in {self.elf_path}"
                )

            if self.verbose:
                print("DWARF information loaded successfully")
                print(
                    f"DWARF version: "
                    f"{self.dwarf_info.config.default_address_size * 8}-bit"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to load DWARF info: {e}") from e

    def parse_die(self, elf_die: ElfDIE, level: int = 0) -> DIE:
        """
        Parse an ELF DIE into our DIE model.

        Args:
            elf_die: The pyelftools DIE object
            level: The nesting level of this DIE

        Returns:
            Parsed DIE object
        """
        # Create the DIE
        die = DIE(
            level=level,
            offset=elf_die.offset,
            global_offset=elf_die.cu.cu_offset + elf_die.offset,
            tag=elf_die.tag,
        )

        # Parse attributes
        for attr_name, attr in elf_die.attributes.items():
            # Handle different attribute types
            value: any = None
            raw_value = str(attr.value)

            if attr.form == "DW_FORM_ref4" or attr.form.startswith("DW_FORM_ref"):
                # This is a reference to another DIE
                ref_offset = attr.value
                # Calculate the global offset (CU offset + reference offset)
                global_offset = elf_die.cu.cu_offset + ref_offset
                value = DIEReference(offset=ref_offset, global_offset=global_offset)
            elif attr.form == "DW_FORM_strp" or attr.form == "DW_FORM_string":
                # String value
                value = attr.value.decode("utf-8") if isinstance(
                    attr.value, bytes
                ) else str(attr.value)
            elif attr.form in ["DW_FORM_data1", "DW_FORM_data2", "DW_FORM_data4",
                              "DW_FORM_data8", "DW_FORM_udata", "DW_FORM_sdata"]:
                # Numeric value
                value = int(attr.value)
            elif attr.form == "DW_FORM_flag" or attr.form == "DW_FORM_flag_present":
                # Boolean value
                value = bool(attr.value)
            elif attr.form == "DW_FORM_addr":
                # Address value
                value = int(attr.value)
            elif attr.form in ["DW_FORM_block", "DW_FORM_block1", "DW_FORM_block2",
                              "DW_FORM_block4", "DW_FORM_exprloc"]:
                # Block of data (used for location expressions, etc.)
                value = bytes(attr.value) if isinstance(attr.value, list) else attr.value
            else:
                # Default: keep as-is
                value = attr.value

            die.attributes[attr_name] = DWARFAttribute(
                name=attr_name, value=value, raw_value=raw_value
            )

        return die

    def parse_compilation_unit(self, cu: any) -> CompilationUnit:
        """
        Parse a compilation unit and all its DIEs.

        Args:
            cu: The pyelftools compilation unit

        Returns:
            Parsed CompilationUnit object
        """
        comp_unit = CompilationUnit(
            offset=cu.cu_offset,
            size=cu.size,
            version=cu.header.version,
            address_size=cu.header.address_size,
        )

        # Parse all DIEs in this CU
        def parse_die_recursive(elf_die: ElfDIE, level: int, parent: Optional[DIE]) -> DIE:
            die = self.parse_die(elf_die, level)
            die.parent = parent
            comp_unit.dies.append(die)

            # Parse children
            for child in elf_die.iter_children():
                child_die = parse_die_recursive(child, level + 1, die)
                die.children.append(child_die)

            return die

        # Start parsing from the top-level DIE of the CU
        top_die = cu.get_top_DIE()
        parse_die_recursive(top_die, 0, None)

        return comp_unit

    def parse_all_compilation_units(self) -> list[CompilationUnit]:
        """
        Parse all compilation units in the DWARF info.

        Returns:
            List of parsed CompilationUnit objects
        """
        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")

        compilation_units: list[CompilationUnit] = []

        if self.verbose:
            print("Parsing compilation units...")

        for cu in self.dwarf_info.iter_CUs():
            try:
                comp_unit = self.parse_compilation_unit(cu)
                compilation_units.append(comp_unit)

                if self.verbose:
                    print(
                        f"  Parsed CU at offset 0x{comp_unit.offset:08x} "
                        f"({len(comp_unit.dies)} DIEs)"
                    )
            except Exception as e:
                if self.verbose:
                    print(
                        f"  Warning: Failed to parse CU at offset "
                        f"0x{cu.cu_offset:08x}: {e}",
                        file=sys.stderr,
                    )

        if self.verbose:
            print(f"Total compilation units parsed: {len(compilation_units)}")

        return compilation_units

    def iter_compilation_units(self) -> "Generator[CompilationUnit, None, None]":
        """
        Iterator that yields compilation units one by one for efficient scanning.

        This allows processing CUs incrementally without loading all into memory,
        which is crucial for performance when searching for specific symbols.

        Yields:
            CompilationUnit objects one at a time
        """
        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")

        for cu in self.dwarf_info.iter_CUs():
            try:
                comp_unit = self.parse_compilation_unit(cu)
                yield comp_unit
            except Exception as e:
                if self.verbose:
                    print(
                        f"  Warning: Failed to parse CU at offset "
                        f"0x{cu.cu_offset:08x}: {e}",
                        file=sys.stderr,
                    )
                continue

    def close(self) -> None:
        """Close the ELF file."""
        if hasattr(self, "file_handle"):
            self.file_handle.close()

    def __enter__(self) -> "DWARFParser":
        """Context manager entry."""
        self.open()
        self.load_dwarf_info()
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any) -> None:
        """Context manager exit."""
        self.close()

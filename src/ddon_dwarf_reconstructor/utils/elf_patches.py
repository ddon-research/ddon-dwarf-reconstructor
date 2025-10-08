"""Patches for pyelftools to handle PS4 ELF files with non-standard sections."""

from typing import Any

from elftools.common.exceptions import ELFError
from elftools.elf import elffile


def patch_pyelftools_for_ps4() -> None:
    """
    Apply monkey patches to pyelftools to handle PS4 ELF files.

    PS4 ELF files may have non-standard or malformed sections that cause
    pyelftools to fail. This patches the library to be more lenient.
    """
    # Save original methods
    original_make_section = elffile.ELFFile._make_section
    original_get_section = elffile.ELFFile.get_section

    def patched_make_section(self: elffile.ELFFile, section_header: Any) -> Any:
        """Patched version of _make_section that handles PS4-specific issues."""
        try:
            return original_make_section(self, section_header)
        except ELFError as e:
            # If we get an error about unexpected section types, create a generic section
            if "Unexpected section type" in str(e):
                # Return a generic Section instead of failing
                from elftools.elf.sections import Section

                return Section(section_header, "", self)
            raise

    def patched_get_section(
        self: elffile.ELFFile, section_index: int, type_filter: Any = None
    ) -> Any:
        """Patched version of get_section that handles PS4-specific issues."""
        try:
            return original_get_section(self, section_index, type_filter)
        except ELFError as e:
            # If we get an error about unexpected section types and no type filter, be lenient
            if "Unexpected section type" in str(e) and type_filter is None:
                # Try to create a generic section
                section_header = self._get_section_header(section_index)
                from elftools.elf.sections import Section

                return Section(section_header, "", self)
            raise

    # Apply patches
    elffile.ELFFile._make_section = patched_make_section  # type: ignore[method-assign]
    elffile.ELFFile.get_section = patched_get_section  # type: ignore[method-assign]

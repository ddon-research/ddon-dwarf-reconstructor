"""Enhanced patches for pyelftools to handle PS4 ELF files with non-standard sections.

This module provides comprehensive patches to handle PS4-specific ELF format issues:
1. Non-standard section types that cause pyelftools to fail
2. Dynamic sections with invalid sh_link pointing to NULL sections  
3. PS4-specific SCE (Sony Computer Entertainment) dynamic tags and sections

The patches are designed to be non-invasive and fallback gracefully while preserving
the ability to extract DWARF debugging information from PS4 ELF files.
"""

from typing import Any

from elftools.common.exceptions import ELFError
from elftools.elf import elffile
from elftools.elf.dynamic import DynamicSection
from elftools.elf.sections import Section, NullSection


def patch_pyelftools_for_ps4() -> None:
    """
    Apply comprehensive monkey patches to pyelftools to handle PS4 ELF files.

    PS4 ELF files have several non-standard characteristics:
    - Custom Sony Computer Entertainment (SCE) section names and types
    - Dynamic sections with sh_link=0 pointing to NULL sections instead of string tables
    - Custom program header types (PT_SCE_*)
    - Non-standard dynamic tags (DT_SCE_*)

    This patches the library to be more lenient while preserving functionality.
    """
    # Save original methods
    original_make_section = elffile.ELFFile._make_section
    original_get_section = elffile.ELFFile.get_section
    original_dynamic_init = DynamicSection.__init__

    def patched_make_section(self: elffile.ELFFile, section_header: Any) -> Any:
        """
        Patched version of _make_section that handles PS4-specific issues.
        
        Specifically handles unexpected section types by creating generic sections.
        """
        try:
            return original_make_section(self, section_header)
        except ELFError as e:
            error_msg = str(e)
            
            # Handle unexpected section types
            if "Unexpected section type" in error_msg:
                # Return a generic Section instead of failing
                name = self._get_section_name(section_header)
                return Section(section_header, name, self)
            
            # Re-raise other ELF errors
            raise

    def patched_get_section(
        self: elffile.ELFFile,
        section_index: int,
        type_filter: Any = None,
    ) -> Any:
        """
        Patched version of get_section that handles PS4-specific issues.
        
        Specifically handles NULL section references in PS4 dynamic sections.
        """
        try:
            return original_get_section(self, section_index, type_filter)
        except ELFError as e:
            error_msg = str(e)
            
            # Handle unexpected section types when no specific type is required
            if "Unexpected section type" in error_msg and type_filter is None:
                # Try to create a generic section
                section_header = self._get_section_header(section_index)
                name = self._get_section_name(section_header)
                return Section(section_header, name, self)
            
            # Handle PS4 dynamic section linking to NULL section
            if ("Unexpected section type SHT_NULL" in error_msg and type_filter and
                ('SHT_STRTAB' in str(type_filter) or 'SHT_NOBITS' in str(type_filter))):
                # PS4 ELFs may have dynamic sections with sh_link=0 (NULL section)
                # In this case, return a NullSection to prevent crashes
                section_header = self._get_section_header(section_index)
                name = self._get_section_name(section_header)
                return NullSection(section_header, name, self)
            
            # Re-raise other ELF errors
            raise

    def patched_dynamic_init(
        self: DynamicSection,
        header: Any,
        name: str,
        elffile: elffile.ELFFile,
    ) -> None:
        """
        Patched version of DynamicSection.__init__ that handles PS4-specific issues.
        
        PS4 ELFs often have dynamic sections with sh_link=0, pointing to the NULL section
        instead of a proper string table. This patch handles that gracefully.
        """
        Section.__init__(self, header, name, elffile)
        
        try:
            # Try the normal path first
            stringtable = elffile.get_section(header['sh_link'], ('SHT_STRTAB', 'SHT_NOBITS'))
        except ELFError as e:
            if "Unexpected section type SHT_NULL" in str(e):
                # PS4 ELF: sh_link points to NULL section, use NullSection as fallback
                stringtable = elffile.get_section(header['sh_link'])
            else:
                raise
        
        # Import here to avoid circular imports
        from elftools.elf.dynamic import Dynamic
        Dynamic.__init__(
            self,
            self.stream,
            self.elffile,
            stringtable,
            self['sh_offset'],
            self['sh_type'] == 'SHT_NOBITS'
        )

    # Apply patches
    elffile.ELFFile._make_section = patched_make_section  # type: ignore[method-assign]
    elffile.ELFFile.get_section = patched_get_section  # type: ignore[method-assign]
    DynamicSection.__init__ = patched_dynamic_init  # type: ignore[method-assign]

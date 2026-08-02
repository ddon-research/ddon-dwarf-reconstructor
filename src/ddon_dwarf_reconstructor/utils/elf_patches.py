"""Compatibility patches for PS4-specific pyelftools ELF sections."""

from __future__ import annotations

from collections.abc import Callable, Container
from typing import Any, cast

from elftools.common.exceptions import ELFError
from elftools.elf import elffile
from elftools.elf.dynamic import DynamicSection
from elftools.elf.sections import NullSection, Section


def patch_pyelftools_for_ps4() -> None:
    """Apply narrowly scoped PS4 section and dynamic-linker fallbacks."""
    original_make_section = elffile.ELFFile._make_section
    original_get_section = elffile.ELFFile.get_section
    elffile.ELFFile._make_section = _make_section_patch(original_make_section)  # type: ignore[method-assign]
    elffile.ELFFile.get_section = _get_section_patch(original_get_section)  # type: ignore[method-assign]
    DynamicSection.__init__ = _dynamic_init_patch()  # type: ignore[method-assign]


def _make_section_patch(original: Callable[..., Any]) -> Callable[..., Any]:
    def patched_make_section(self: elffile.ELFFile, section_header: Any) -> Any:
        try:
            return original(self, section_header)
        except ELFError as error:
            if "Unexpected section type" not in str(error):
                raise
            name = self._get_section_name(section_header)
            return Section(section_header, name, self)

    return patched_make_section


def _get_section_patch(original: Callable[..., Any]) -> Callable[..., Any]:
    def patched_get_section(
        self: elffile.ELFFile,
        n: int,
        type: Container[str] | None = None,
    ) -> Section:
        try:
            return cast(Section, original(self, n, type))
        except ELFError as error:
            error_text = str(error)
            if "Unexpected section type" in error_text and type is None:
                return _generic_section(self, n)
            if _is_null_dynamic_link(error_text, type):
                return _null_section(self, n)
            raise

    return patched_get_section


def _is_null_dynamic_link(error_text: str, section_type: Container[str] | None) -> bool:
    return (
        "Unexpected section type SHT_NULL" in error_text
        and section_type is not None
        and ("SHT_STRTAB" in str(section_type) or "SHT_NOBITS" in str(section_type))
    )


def _generic_section(elf: elffile.ELFFile, index: int) -> Section:
    header = elf._get_section_header(index)
    return Section(header, elf._get_section_name(header), elf)


def _null_section(elf: elffile.ELFFile, index: int) -> NullSection:
    header = elf._get_section_header(index)
    return NullSection(header, elf._get_section_name(header), elf)


def _dynamic_init_patch() -> Callable[..., Any]:
    def patched_dynamic_init(
        self: DynamicSection,
        header: Any,
        name: str,
        elffile: elffile.ELFFile,
    ) -> None:
        Section.__init__(self, header, name, elffile)
        stringtable = _dynamic_string_table(elffile, header)
        from elftools.elf.dynamic import Dynamic

        Dynamic.__init__(
            self,
            self.stream,
            self.elffile,
            stringtable,
            self["sh_offset"],
            self["sh_type"] == "SHT_NOBITS",
        )

    return patched_dynamic_init


def _dynamic_string_table(elffile: elffile.ELFFile, header: Any) -> Section:
    try:
        return elffile.get_section(header["sh_link"], ("SHT_STRTAB", "SHT_NOBITS"))
    except ELFError as error:
        if "Unexpected section type SHT_NULL" not in str(error):
            raise
        return elffile.get_section(header["sh_link"])

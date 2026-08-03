"""Explicit, read-only ELF/DWARF producer evidence inspection."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

from ..core.dwarf import decode_dwarf_string
from .elf_platform import PlatformDetector


def inspect_elf(path: Path) -> dict[str, Any]:
    """Inspect one ELF and all CU headers without retaining its DIE graph."""
    with path.open("rb") as stream:
        return inspect_open_elf(ELFFile(stream), str(path.resolve()))


def inspect_open_elf(elf: ELFFile, path: str = "<open ELF>") -> dict[str, Any]:
    """Return stable ELF header and DWARF producer/version evidence."""
    header = elf.header
    return {
        "path": path,
        "platform": PlatformDetector.detect_elf(elf, path).value,
        "elf": _elf_summary(elf, header),
        "dwarf": _dwarf_summary(elf),
    }


def _elf_summary(elf: ELFFile, header: object) -> dict[str, str]:
    return {
        "class": str(getattr(elf, "elfclass", "unknown")),
        "machine": str(_header_value(header, "e_machine", "unknown")),
        "type": str(_header_value(header, "e_type", "unknown")),
        "osabi": str(_osabi(header)),
        "endianness": "little" if elf.little_endian else "big",
    }


def _dwarf_summary(elf: ELFFile) -> dict[str, Any]:
    dwarf_versions, producers, languages, cu_offsets = _collect_cu_evidence(elf)
    return {
        "cu_count": len(cu_offsets),
        "first_cu_offset": cu_offsets[0] if cu_offsets else None,
        "last_cu_offset": cu_offsets[-1] if cu_offsets else None,
        "versions": dict(sorted((str(key), value) for key, value in dwarf_versions.items())),
        "version_consistent": len(dwarf_versions) <= 1,
        "producers": dict(sorted(producers.items())),
        "languages": dict(sorted(languages.items())),
        "debug_sections": _debug_sections(elf),
    }


def _collect_cu_evidence(
    elf: ELFFile,
) -> tuple[Counter[int], Counter[str], Counter[str], list[int]]:
    dwarf_versions: Counter[int] = Counter()
    producers: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    cu_offsets: list[int] = []
    if not elf.has_dwarf_info():
        return dwarf_versions, producers, languages, cu_offsets
    for cu in elf.get_dwarf_info().iter_CUs():
        _record_cu_evidence(cu, dwarf_versions, producers, languages, cu_offsets)
    return dwarf_versions, producers, languages, cu_offsets


def _record_cu_evidence(
    cu: Any,
    dwarf_versions: Counter[int],
    producers: Counter[str],
    languages: Counter[str],
    cu_offsets: list[int],
) -> None:
    cu_offsets.append(cu.cu_offset)
    version = _header_value(cu.header, "version")
    if isinstance(version, int):
        dwarf_versions[version] += 1
    top_die = cu.get_top_DIE()
    producer = _attribute_text(top_die, "DW_AT_producer")
    if producer:
        producers[producer] += 1
    language = _attribute_value(top_die, "DW_AT_language")
    if language is not None:
        languages[str(language)] += 1


def _debug_sections(elf: ELFFile) -> list[str]:
    return sorted(
        section.name
        for section in elf.iter_sections()
        if isinstance(section.name, str) and section.name.startswith(".debug_")
    )


def _header_value(header: object, key: str, default: object = None) -> object:
    try:
        return header[key]  # type: ignore[index]
    except KeyError, TypeError:
        return default


def _osabi(header: object) -> object:
    ident = _header_value(header, "e_ident", {})
    return _header_value(ident, "EI_OSABI", "unknown")


def _attribute_value(die: object, name: str) -> object:
    attributes = getattr(die, "attributes", {})
    attribute = attributes.get(name)
    return getattr(attribute, "value", None) if attribute is not None else None


def _attribute_text(die: object, name: str) -> str:
    value = _attribute_value(die, name)
    return decode_dwarf_string(value) if value is not None else ""

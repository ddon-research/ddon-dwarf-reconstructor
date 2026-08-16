"""Pure PS4 relocation, symbol, and opaque NID evidence evaluation."""

from __future__ import annotations

import struct
from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from ..domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisRelocationEntry,
)
from ..domain.models.implementation_validation import (
    LoadImageProfile,
    MappedSegment,
    RelocationApplication,
    ValidationStatus,
)
from .implementation_load_image import runtime_address, virtual_to_file_offset
from .implementation_nids import nid_bindings
from .orbis_sdk_definitions import PT_SCE_DYNLIBDATA

RELOCATION_EVALUATOR_VERSION = "1.1"

_RELOCATION_SPECS: dict[int, tuple[int, str, bool]] = {
    0: (0, "NONE", False),
    1: (8, "S + A", False),
    2: (4, "S + A - P", True),
    3: (4, "G + A", False),
    4: (4, "L + A - P", True),
    5: (0, "COPY", False),
    6: (8, "S", False),
    7: (8, "S", False),
    8: (8, "B + A", False),
    9: (4, "G + A - P", True),
    10: (4, "S + A", False),
    11: (4, "S + A", True),
    12: (2, "S + A", False),
    13: (2, "S + A - P", True),
    14: (1, "S + A", True),
    15: (1, "S + A - P", True),
    16: (8, "TLS_MODULE_ID", False),
    17: (8, "TLS_OFFSET + A", False),
    18: (8, "TLS_OFFSET + A", False),
    19: (4, "TLS_GD_GOT + A - P", True),
    20: (4, "TLS_LD_GOT + A - P", True),
    21: (4, "TLS_OFFSET + A", True),
    22: (4, "TLS_IE_GOT + A - P", True),
    23: (4, "TLS_OFFSET + A", True),
    24: (8, "S + A - P", True),
    25: (8, "S + A - GOT", True),
    26: (4, "GOT + A - P", True),
    27: (8, "GOT + A", False),
    28: (8, "GOT + A - P", True),
    29: (8, "GOT + A - P", True),
    30: (8, "GOTPLT + A", False),
    31: (8, "L + A - GOT", True),
    34: (4, "TLS_DESC_GOT + A - P", True),
    35: (0, "TLS_DESC_CALL", False),
    36: (16, "TLS_DESC", False),
    37: (8, "IRELATIVE", False),
    38: (8, "B + A", False),
    40: (4, "ORBS_GOTPCREL_LOAD", True),
}


@dataclass(frozen=True, slots=True)
class RelocationIndex:
    """Address-ordered relocation view for repeated method interval lookups."""

    offsets: tuple[int, ...]
    entries: tuple[Any, ...]

    @classmethod
    def build(cls, entries: Iterable[Any]) -> RelocationIndex:
        ordered = tuple(
            sorted(
                entries,
                key=lambda item: (int(item.relocation_offset), str(item.relocation_id)),
            )
        )
        return cls(
            tuple(int(item.relocation_offset) for item in ordered),
            ordered,
        )

    def select(self, start: int | None, end: int | None) -> tuple[Any, ...]:
        if start is None or end is None or end <= start:
            return ()
        left = bisect_left(self.offsets, start)
        right = bisect_left(self.offsets, end)
        return self.entries[left:right]


def evaluate_relocations(
    source: Path,
    profile: LoadImageProfile,
    segments: tuple[MappedSegment, ...],
    entries: Iterable[OrbisRelocationEntry],
    dynamic_tags: tuple[OrbisDynamicTag, ...],
) -> tuple[tuple[RelocationApplication, ...], dict[int, tuple[str | None, int]]]:
    """Evaluate known relocation formulas and retain all unresolved reasons."""
    symbols = _dynamic_symbol_values(source, dynamic_tags)
    relocation_entries = tuple(entries)
    got_values = _got_slot_values(profile, relocation_entries)
    got_base = _got_base(profile, dynamic_tags)
    with source.open("rb") as stream:
        results = tuple(
            _evaluate_entry(
                stream,
                profile,
                segments,
                entry,
                symbols,
                got_values,
                got_base,
            )
            for entry in relocation_entries
        )
    return results, symbols


def _evaluate_entry(
    stream: BinaryIO,
    profile: LoadImageProfile,
    segments: tuple[MappedSegment, ...],
    entry: OrbisRelocationEntry,
    symbols: dict[int, tuple[str | None, int]],
    got_values: dict[int, int],
    got_base: int | None,
) -> RelocationApplication:
    width, formula, signed = _relocation_spec(entry)
    file_offset = virtual_to_file_offset(segments, entry.offset, width or 1)
    original = (
        _read_bytes(stream, file_offset, width) if file_offset is not None and width else None
    )
    runtime = runtime_address(profile, entry.offset)
    symbol_name, symbol_value = symbols.get(entry.symbol_index, (entry.symbol_name, 0))
    status, value, diagnostics = _evaluate_entry_value(
        entry,
        profile,
        runtime,
        file_offset,
        original,
        symbol_value,
        symbols,
        got_values,
        got_base,
    )
    evaluated = _encode_value(value, width, signed) if value is not None else None
    return RelocationApplication(
        relocation_id=entry.relocation_id,
        relocation_code=entry.relocation_code,
        relocation_name=entry.relocation_name,
        relocation_offset=entry.offset,
        target_runtime_address=runtime,
        target_file_offset=file_offset,
        width_bytes=width,
        formula=formula,
        addend=entry.addend,
        symbol_index=entry.symbol_index,
        symbol_name=symbol_name,
        symbol_value=symbol_value if entry.symbol_index in symbols else None,
        original_bytes=original,
        evaluated_value=value,
        evaluated_bytes=evaluated,
        status=status,
        diagnostics=tuple(diagnostics),
    )


def _relocation_spec(
    entry: OrbisRelocationEntry,
) -> tuple[int | None, str | None, bool]:
    spec = _RELOCATION_SPECS.get(entry.relocation_code)
    return (spec[0], spec[1], spec[2]) if spec is not None else (None, None, False)


def _evaluate_entry_value(
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    runtime: int | None,
    file_offset: int | None,
    original: str | None,
    symbol_value: int,
    symbols: dict[int, tuple[str | None, int]],
    got_values: dict[int, int],
    got_base: int | None,
) -> tuple[ValidationStatus, int | None, list[str]]:
    gate = _entry_value_gate(entry, profile, file_offset, original, symbols)
    if gate is not None:
        status, diagnostic = gate
        return status, None, [diagnostic]
    diagnostics: list[str] = []
    value = _formula_value(
        entry,
        profile,
        runtime,
        symbol_value,
        got_values.get(entry.symbol_index),
        got_base,
        diagnostics,
    )
    width, _formula, signed = _relocation_spec(entry)
    return _value_status(value, width, signed, diagnostics), value, diagnostics


def _entry_value_gate(
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    file_offset: int | None,
    original: str | None,
    symbols: dict[int, tuple[str | None, int]],
) -> tuple[ValidationStatus, str] | None:
    """Reject relocation inputs whose loader prerequisites are not observed."""
    code = entry.relocation_code
    if code not in _RELOCATION_SPECS:
        return (
            ValidationStatus.NOT_OBSERVED,
            "relocation formula is not present in the reviewed SDK subset",
        )
    location_gate = _relocation_location_gate(file_offset, original)
    if location_gate is not None:
        return location_gate
    return _relocation_formula_gate(entry, profile, symbols)


def _relocation_location_gate(
    file_offset: int | None, original: str | None
) -> tuple[ValidationStatus, str] | None:
    if file_offset is None:
        return ValidationStatus.PARTIAL, "relocation target is outside PT_LOAD file-backed bytes"
    if original is None:
        return ValidationStatus.PARTIAL, "relocation target bytes are truncated or unavailable"
    return None


def _relocation_formula_gate(
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    symbols: dict[int, tuple[str | None, int]],
) -> tuple[ValidationStatus, str] | None:
    code = entry.relocation_code
    if code == 40:
        return (
            ValidationStatus.NOT_OBSERVED,
            "Orbis GOT load instruction patch semantics remain unverified",
        )
    got_codes = {3, 9, 25, 26, 27, 28, 29, 30, 31}
    if code not in {0, 8, 37, 38, 40, *got_codes} and entry.symbol_index not in symbols:
        return ValidationStatus.NOT_OBSERVED, "dynamic symbol value is unavailable"
    if code == 25 and entry.symbol_index not in symbols:
        return ValidationStatus.NOT_OBSERVED, "GOT-relative relocation has no dynamic symbol value"
    if code in {8, 37, 38} and profile.load_bias is None:
        return ValidationStatus.NOT_OBSERVED, "R_X86_64_RELATIVE requires an explicit load bias"
    if code in {0, 5, 16, 19, 20, 22, 34, 35, 36, 37}:
        return (
            ValidationStatus.NOT_OBSERVED,
            "relocation requires loader or TLS state outside the ELF evidence",
        )
    return None


def _unavailable_value(message: str) -> tuple[ValidationStatus, None, list[str]]:
    return ValidationStatus.NOT_OBSERVED, None, [message]


def _partial_value(message: str) -> tuple[ValidationStatus, None, list[str]]:
    return ValidationStatus.PARTIAL, None, [message]


def _formula_value(
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    runtime: int | None,
    symbol_value: int,
    got_value: int | None,
    got_base: int | None,
    diagnostics: list[str],
) -> int | None:
    handled, value = _simple_formula_value(entry, profile, runtime, symbol_value, diagnostics)
    if handled:
        return value
    if entry.relocation_code in {3, 27, 9, 26, 28, 29, 25, 30}:
        return _got_formula_value(
            entry.relocation_code,
            entry,
            profile,
            runtime,
            symbol_value,
            got_value,
            got_base,
            diagnostics,
        )
    diagnostics.append("relocation needs GOT, TLS, or linker state not present in the source")
    return None


def _simple_formula_value(
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    runtime: int | None,
    symbol_value: int,
    diagnostics: list[str],
) -> tuple[bool, int | None]:
    code = entry.relocation_code
    if code in {8, 38}:
        return True, (profile.load_bias or 0) + entry.addend
    if code in {1, 10, 11}:
        return True, symbol_value + (profile.load_bias or 0) + entry.addend
    if code in {6, 7}:
        return True, symbol_value + (profile.load_bias or 0)
    if code in {2, 13, 15, 24}:
        return True, _pc_relative_value(
            entry, profile.load_bias, runtime, symbol_value, diagnostics
        )
    if code in {12, 14}:
        return True, symbol_value + (profile.load_bias or 0) + entry.addend
    return False, None


def _got_formula_value(
    code: int,
    entry: OrbisRelocationEntry,
    profile: LoadImageProfile,
    runtime: int | None,
    symbol_value: int,
    got_value: int | None,
    got_base: int | None,
    diagnostics: list[str],
) -> int | None:
    if code in {3, 27}:
        if got_value is None:
            diagnostics.append("GOT slot address is unavailable from source relocation evidence")
            return None
        return got_value + entry.addend
    if code in {9, 26, 28, 29}:
        if got_value is None or runtime is None:
            diagnostics.append("GOT slot or runtime PC is unavailable from source evidence")
            return None
        return got_value + entry.addend - runtime
    if got_base is None:
        diagnostics.append("DT_SCE_PLTGOT did not provide a GOT base address")
        return None
    if code == 25:
        return symbol_value + (profile.load_bias or 0) + entry.addend - got_base
    return got_base + entry.addend


def _pc_relative_value(
    entry: OrbisRelocationEntry,
    bias: int | None,
    runtime: int | None,
    symbol_value: int,
    diagnostics: list[str],
) -> int | None:
    if runtime is None:
        diagnostics.append("PC-relative relocation has no selected runtime address")
        return None
    return symbol_value + (bias or 0) + entry.addend - runtime


def _got_slot_values(
    profile: LoadImageProfile, entries: tuple[OrbisRelocationEntry, ...]
) -> dict[int, int]:
    """Map symbols to GOT slots only when a dynamic slot relocation proves it."""
    values: dict[int, int] = {}
    for entry in entries:
        if entry.relocation_code not in {6, 7}:
            continue
        relocation_name = (entry.relocation_name or "").upper()
        if "GLOB_DAT" not in relocation_name and "JUMP_SLOT" not in relocation_name:
            continue
        runtime = runtime_address(profile, entry.offset)
        if runtime is None or entry.symbol_index in values:
            continue
        values[entry.symbol_index] = runtime
    return values


def _got_base(profile: LoadImageProfile, dynamic_tags: tuple[OrbisDynamicTag, ...]) -> int | None:
    value = next(
        (tag.value for tag in dynamic_tags if tag.name == "DT_SCE_PLTGOT"),
        None,
    )
    return runtime_address(profile, value) if isinstance(value, int) else None


def _value_status(
    value: int | None, width: int | None, signed: bool, diagnostics: list[str]
) -> ValidationStatus:
    if value is None:
        return ValidationStatus.NOT_OBSERVED
    if width is None:
        return ValidationStatus.PARTIAL
    bits = width * 8
    lower = -(1 << (bits - 1)) if signed else 0
    upper = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1
    if not lower <= value <= upper:
        diagnostics.append(f"evaluated value 0x{value:x} overflows {bits}-bit relocation field")
        return ValidationStatus.FAILED
    return ValidationStatus.OBSERVED


def _encode_value(value: int | None, width: int | None, signed: bool) -> str | None:
    if value is None or width is None:
        return None
    return value.to_bytes(width, "little", signed=signed).hex()


def _read_bytes(stream: BinaryIO, offset: int | None, width: int | None) -> str | None:
    if offset is None or width is None:
        return None
    seek = stream.seek
    read = stream.read
    seek(offset)
    data = read(width)
    return data.hex() if len(data) == width else None


def _dynamic_symbol_values(
    source: Path, dynamic_tags: tuple[OrbisDynamicTag, ...]
) -> dict[int, tuple[str | None, int]]:
    values = {tag.name: tag.value for tag in dynamic_tags if tag.name}
    table = _dynamic_table_spec(values)
    if table is None:
        return {}
    with source.open("rb") as stream:
        elf = _open_elf(stream)
        dynlib_segment = _dynlib_segment(elf.iter_segments())
        if dynlib_segment is None:
            return {}
        offsets = _dynamic_offsets(dynlib_segment.header, table)
        if offsets is None:
            return {}
        strings, data = _read_dynamic_tables(stream, offsets)
    return _unpack_symbols(strings, data, table[1], table[2])


def _dynamic_table_spec(
    values: dict[str, int],
) -> tuple[int, int, int, int, int] | None:
    address = values.get("DT_SCE_SYMTAB")
    size = values.get("DT_SCE_SYMTABSZ")
    entry_size = values.get("DT_SCE_SYMENT", 24)
    string_address = values.get("DT_SCE_STRTAB")
    string_size = values.get("DT_SCE_STRSZ", 0)
    if not isinstance(address, int) or not isinstance(size, int):
        return None
    if not isinstance(entry_size, int) or entry_size != 24:
        return None
    if not isinstance(string_address, int):
        return None
    if not isinstance(string_size, int):
        string_size = 0
    return address, size, entry_size, string_address, string_size


def _dynlib_segment(segments: Iterable[Any]) -> Any | None:
    return next(
        (
            segment
            for segment in segments
            if segment.header["p_type"] == PT_SCE_DYNLIBDATA
            or segment.header["p_type"] == "PT_SCE_DYNLIBDATA"
        ),
        None,
    )


def _dynamic_offsets(
    header: Any,
    table: tuple[int, int, int, int, int],
) -> tuple[int, int, int, int] | None:
    address, size, entry_size, string_address, string_size = table
    symbol_offset = _relative_offset(header, address, size)
    string_offset = _relative_offset(header, string_address, string_size)
    if symbol_offset is None or string_offset is None or size % entry_size:
        return None
    return symbol_offset, string_offset, size, string_size


def _read_dynamic_tables(
    stream: BinaryIO,
    offsets: tuple[int, int, int, int],
) -> tuple[bytes, bytes]:
    symbol_offset, string_offset, size, string_size = offsets
    stream.seek(string_offset)
    strings = stream.read(string_size)
    stream.seek(symbol_offset)
    data = stream.read(size)
    return strings, data


def _unpack_symbols(
    strings: bytes,
    data: bytes,
    size: int,
    entry_size: int,
) -> dict[int, tuple[str | None, int]]:
    unpack = struct.Struct("<IBBHQQ")
    result: dict[int, tuple[str | None, int]] = {}
    for index in range(size // entry_size):
        name_offset, _, _, _, value, _ = unpack.unpack_from(data, index * entry_size)
        result[index] = (_c_string(strings, name_offset), value)
    return result


def _open_elf(stream: BinaryIO) -> Any:
    from elftools.elf.elffile import ELFFile

    return ELFFile(stream)


def _relative_offset(header: Any, address: int, size: int) -> int | None:
    virtual = int(header["p_vaddr"])
    file_size = int(header["p_filesz"])
    relative = address - virtual
    if relative < 0 or size < 0 or relative + size > file_size:
        return None
    return int(header["p_offset"]) + relative


def _c_string(data: bytes, offset: int) -> str | None:
    if offset < 0 or offset >= len(data):
        return None
    end = data.find(b"\0", offset)
    if end < 0:
        return None
    return data[offset:end].decode("utf-8", errors="replace")


__all__ = [
    "RELOCATION_EVALUATOR_VERSION",
    "RelocationIndex",
    "evaluate_relocations",
    "nid_bindings",
]

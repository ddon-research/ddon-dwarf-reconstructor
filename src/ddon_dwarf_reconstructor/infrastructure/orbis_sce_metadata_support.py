"""Small, typed helpers shared by the SCE metadata reader and its cache."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from elftools.elf.elffile import ELFFile

from ..domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisRelocationEntry,
    OrbisRelocationTable,
    OrbisSceSegment,
    OrbisSdkDefinitionIdentity,
    OrbisToolIdentity,
)
from .orbis_objdump_profiles import SCE_METADATA_PARSER_VERSION
from .orbis_sdk_definitions import (
    PT_GNU_RELRO,
    PT_SCE_DYNLIBDATA,
    RELA_ENTRY_SIZE,
    RELOCATION_NAMES,
)


@dataclass(frozen=True, slots=True)
class Segment:
    """Relevant SCE program-segment geometry."""

    kind: str
    type_code: int
    file_offset: int
    virtual_address: int
    file_size: int
    memory_size: int

    def model(self) -> OrbisSceSegment:
        return OrbisSceSegment(
            self.kind,
            self.type_code,
            self.file_offset,
            self.virtual_address,
            self.file_size,
            self.memory_size,
        )


@dataclass(frozen=True, slots=True)
class _RelocationDescriptor:
    """Validated metadata needed to read one bounded RELA table."""

    address: int | None
    size: int
    entry_size: int
    count: int
    status: str
    diagnostics: tuple[str, ...] = ()


def sce_segments(elf: ELFFile) -> Iterable[Segment]:
    names = {
        PT_SCE_DYNLIBDATA: "PT_SCE_DYNLIBDATA",
        PT_GNU_RELRO: "PT_GNU_RELRO",
    }
    for segment in elf.iter_segments():
        type_code = _segment_type_code(segment.header["p_type"])
        if type_code not in names:
            continue
        yield Segment(
            names[type_code],
            type_code,
            int(segment.header["p_offset"]),
            int(segment.header["p_vaddr"]),
            int(segment.header["p_filesz"]),
            int(segment.header["p_memsz"]),
        )


def _segment_type_code(value: object) -> int:
    if isinstance(value, int):
        return value
    if value == "PT_SCE_DYNLIBDATA":
        return PT_SCE_DYNLIBDATA
    if value == "PT_GNU_RELRO":
        return PT_GNU_RELRO
    return -1


def metadata_status(tables: list[OrbisRelocationTable]) -> str:
    statuses = {table.status for table in tables}
    if "malformed" in statuses:
        return "malformed"
    if "partial" in statuses or "not_observed" in statuses:
        return "partial" if "observed" in statuses else "not_observed"
    return "observed"


def parse_relocation_table(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    dynlib: Segment,
    values: dict[str, int],
    table_name: str,
    address_tag: str,
    size_tag: str,
    symbols: dict[int, str | None],
    on_entry: Callable[[OrbisRelocationEntry], None],
) -> OrbisRelocationTable:
    """Parse one SCE RELA table after validating its descriptor."""
    descriptor = _relocation_descriptor(table_name, address_tag, size_tag, values)
    if descriptor.status != "ready":
        return _descriptor_table(table_name, address_tag, descriptor)
    address = descriptor.address
    if address is None:
        raise AssertionError("ready relocation descriptor has no address")
    diagnostics = list(descriptor.diagnostics)
    file_offset = relative_file_offset(dynlib, address, descriptor.size, file_size)
    if file_offset is None:
        diagnostics.append(f"{table_name} range is outside PT_SCE_DYNLIBDATA or the ELF file")
        return _table(
            table_name,
            address_tag,
            address,
            None,
            descriptor.size,
            descriptor.entry_size,
            descriptor.count,
            "malformed",
            diagnostics,
        )
    actual_count, read_diagnostics = _read_relocation_entries(
        stream,
        file_size,
        endian,
        table_name,
        symbols,
        descriptor,
        file_offset,
        on_entry,
    )
    diagnostics.extend(read_diagnostics)
    status = "partial" if read_diagnostics else "observed"
    return _table(
        table_name,
        address_tag,
        address,
        file_offset,
        descriptor.size,
        descriptor.entry_size,
        actual_count,
        status,
        diagnostics,
    )


def _relocation_descriptor(
    table_name: str,
    address_tag: str,
    size_tag: str,
    values: dict[str, int],
) -> _RelocationDescriptor:
    address = values.get(address_tag)
    size = values.get(size_tag)
    entry_size = values.get("DT_SCE_RELAENT")
    if address is None:
        return _unobserved_descriptor(size, entry_size)
    missing = _missing_descriptor_tags(size_tag, size, entry_size)
    if missing:
        return _malformed_descriptor(table_name, address, size, entry_size, missing)
    if size is None or entry_size is None:
        raise AssertionError("complete relocation descriptor has missing dimensions")
    count = size // entry_size if entry_size else 0
    if entry_size != RELA_ENTRY_SIZE:
        return _RelocationDescriptor(
            address,
            size,
            entry_size,
            count,
            "malformed",
            (f"{table_name} entry size {entry_size} is not {RELA_ENTRY_SIZE}",),
        )
    return _RelocationDescriptor(
        address,
        size,
        entry_size,
        count,
        "ready",
        tuple(_size_diagnostics(table_name, size, entry_size)),
    )


def _unobserved_descriptor(size: int | None, entry_size: int | None) -> _RelocationDescriptor:
    return _RelocationDescriptor(
        None,
        size if size is not None else 0,
        entry_size if entry_size is not None else RELA_ENTRY_SIZE,
        0,
        "not_observed",
    )


def _missing_descriptor_tags(
    size_tag: str, size: int | None, entry_size: int | None
) -> tuple[str, ...]:
    return tuple(
        tag for tag, value in ((size_tag, size), ("DT_SCE_RELAENT", entry_size)) if value is None
    )


def _malformed_descriptor(
    table_name: str,
    address: int,
    size: int | None,
    entry_size: int | None,
    missing: tuple[str, ...],
) -> _RelocationDescriptor:
    return _RelocationDescriptor(
        address,
        size if size is not None else 0,
        entry_size if entry_size is not None else 0,
        0,
        "malformed",
        tuple(f"{table_name} missing {tag}" for tag in missing),
    )


def _descriptor_table(
    table_name: str, address_tag: str, descriptor: _RelocationDescriptor
) -> OrbisRelocationTable:
    return _table(
        table_name,
        address_tag,
        descriptor.address,
        None,
        descriptor.size,
        descriptor.entry_size,
        descriptor.count,
        descriptor.status,
        descriptor.diagnostics,
    )


def _read_relocation_entries(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    table_name: str,
    symbols: dict[int, str | None],
    descriptor: _RelocationDescriptor,
    file_offset: int,
    on_entry: Callable[[OrbisRelocationEntry], None],
) -> tuple[int, tuple[str, ...]]:
    available = max(0, min(descriptor.size, file_size - file_offset))
    data = read_bounded(stream, file_offset, available, file_size)
    actual_count = min(descriptor.count, len(data) // RELA_ENTRY_SIZE)
    for index in range(actual_count):
        on_entry(_relocation_entry(data, index, endian, table_name, symbols))
    if actual_count == descriptor.count and not descriptor.diagnostics:
        return actual_count, ()
    return actual_count, (f"{table_name} supplied {actual_count} of {descriptor.count} records",)


def _size_diagnostics(table_name: str, size: int, entry_size: int) -> list[str]:
    if size % entry_size:
        return [f"{table_name} size {size} is not divisible by entry size {entry_size}"]
    return []


def _relocation_entry(
    data: bytes,
    index: int,
    endian: str,
    table_name: str,
    symbols: dict[int, str | None],
) -> OrbisRelocationEntry:
    raw = data[index * RELA_ENTRY_SIZE : (index + 1) * RELA_ENTRY_SIZE]
    offset, info, addend = struct.Struct(f"{endian}QQq").unpack(raw)
    symbol_index = info >> 32
    relocation_code = info & 0xFFFFFFFF
    relocation_name = RELOCATION_NAMES.get(relocation_code)
    symbol_name = symbols.get(symbol_index)
    resolution_status = "resolved" if symbol_name else "unresolved"
    if relocation_name is None:
        resolution_status = "unknown_code"
    return OrbisRelocationEntry(
        relocation_id=f"{table_name}-{index:08x}",
        table=table_name,
        index=index,
        offset=offset,
        info=info,
        addend=addend,
        symbol_index=symbol_index,
        relocation_code=relocation_code,
        relocation_name=relocation_name,
        symbol_name=symbol_name,
        raw_bytes=raw.hex(),
        resolution_status=resolution_status,
    )


def _table(
    name: str,
    tag: str,
    virtual_address: int | None,
    file_offset: int | None,
    size: int,
    entry_size: int,
    count: int,
    status: str,
    diagnostics: Iterable[str] = (),
) -> OrbisRelocationTable:
    return OrbisRelocationTable(
        name,
        tag,
        virtual_address,
        file_offset,
        size,
        entry_size,
        count,
        status,
        tuple(diagnostics),
    )


def relative_file_offset(
    segment: Segment, virtual_address: int, size: int, file_size: int
) -> int | None:
    file_offset = segment_relative_file_offset(segment, virtual_address, size)
    if file_offset is None:
        return None
    if file_offset > file_size or size > file_size - file_offset:
        return None
    return file_offset


def segment_relative_file_offset(segment: Segment, virtual_address: int, size: int) -> int | None:
    if virtual_address < segment.virtual_address:
        return None
    relative = virtual_address - segment.virtual_address
    if relative > segment.file_size or size < 0 or size > segment.file_size - relative:
        return None
    return segment.file_offset + relative


def read_bounded(stream: BinaryIO, offset: int, size: int, file_size: int) -> bytes:
    if offset < 0 or size < 0 or offset > file_size or size > file_size - offset:
        raise ValueError(f"ELF range is outside the file: offset={offset} size={size}")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"ELF range is truncated: offset={offset} size={size}")
    return data


def file_size(stream: BinaryIO) -> int:
    current = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(current)
    return size


def string_at(data: bytes, offset: int) -> str | None:
    if offset < 0 or offset >= len(data):
        return None
    end = data.find(b"\0", offset)
    if end < 0:
        return None
    return data[offset:end].decode("utf-8", errors="replace") or None


def in_ranges(value: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= value < end for start, end in ranges)


def cache_key(
    source_sha256: str,
    tool: OrbisToolIdentity,
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None,
) -> str:
    value = {
        "parser_version": SCE_METADATA_PARSER_VERSION,
        "source_sha256": source_sha256,
        "tool": asdict(tool),
        "sdk_definition_identity": (
            asdict(sdk_definition_identity) if sdk_definition_identity is not None else None
        ),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dynamic_tag_from_dict(value: dict[str, object]) -> OrbisDynamicTag:
    return OrbisDynamicTag(
        json_int(value.get("tag")),
        json_string(value.get("name")),
        json_int(value.get("value")),
    )


def segment_from_dict(value: dict[str, object]) -> OrbisSceSegment:
    return OrbisSceSegment(
        str(value["kind"]),
        json_int(value.get("type_code")),
        json_int(value.get("file_offset")),
        json_int(value.get("virtual_address")),
        json_int(value.get("file_size")),
        json_int(value.get("memory_size")),
    )


def table_from_dict(value: dict[str, object]) -> OrbisRelocationTable:
    return OrbisRelocationTable(
        str(value["name"]),
        str(value["tag"]),
        json_optional_int(value.get("virtual_address")),
        json_optional_int(value.get("file_offset")),
        json_int(value.get("size")),
        json_int(value.get("entry_size")),
        json_int(value.get("count")),
        str(value["status"]),
        tuple(str(item) for item in json_list(value.get("diagnostics"))),
    )


def entry_from_dict(value: dict[str, object]) -> OrbisRelocationEntry:
    return OrbisRelocationEntry(
        str(value["relocation_id"]),
        str(value["table"]),
        json_int(value.get("index")),
        json_int(value.get("offset")),
        json_int(value.get("info")),
        json_int(value.get("addend")),
        json_int(value.get("symbol_index")),
        json_int(value.get("relocation_code")),
        json_string(value.get("relocation_name")),
        json_string(value.get("symbol_name")),
        str(value["raw_bytes"]),
        str(value["resolution_status"]),
        tuple(json_int(item) for item in json_list(value.get("instruction_addresses"))),
    )


def json_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def json_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def json_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"Expected JSON integer, got {type(value).__name__}")
    return int(value)


def json_optional_int(value: object) -> int | None:
    return None if value is None else json_int(value)


__all__ = [
    "Segment",
    "cache_key",
    "dynamic_tag_from_dict",
    "entry_from_dict",
    "file_size",
    "in_ranges",
    "json_int",
    "json_list",
    "json_optional_int",
    "json_string",
    "metadata_status",
    "parse_relocation_table",
    "read_bounded",
    "relative_file_offset",
    "sce_segments",
    "segment_from_dict",
    "segment_relative_file_offset",
    "sha256_file",
    "string_at",
    "table_from_dict",
]

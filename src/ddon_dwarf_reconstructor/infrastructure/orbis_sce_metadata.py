"""Bounded decoding of PS4/SCE dynamic metadata and RELA tables.

Orbis binutils remains the instruction authority.  This reader exists because
the PS4 relocation tables are SCE dynamic metadata inside ``PT_SCE_DYNLIBDATA``
and are not conventional ``.rela.*`` sections that generic relocation readers
can consume directly.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisRelocationEntry,
    OrbisRelocationTable,
    OrbisSceSegment,
    OrbisSdkDefinitionIdentity,
    OrbisToolIdentity,
)
from ..utils.elf_patches import patch_pyelftools_for_ps4
from .orbis_objdump_profiles import SCE_METADATA_PARSER_VERSION
from .orbis_sce_metadata_support import (
    Segment as _Segment,
)
from .orbis_sce_metadata_support import (
    cache_key as _cache_key,
)
from .orbis_sce_metadata_support import (
    dynamic_tag_from_dict as _dynamic_tag_from_dict,
)
from .orbis_sce_metadata_support import (
    entry_from_dict as _entry_from_dict,
)
from .orbis_sce_metadata_support import (
    file_size as _file_size,
)
from .orbis_sce_metadata_support import (
    in_ranges as _in_ranges,
)
from .orbis_sce_metadata_support import (
    json_int as _json_int,
)
from .orbis_sce_metadata_support import (
    json_list as _json_list,
)
from .orbis_sce_metadata_support import (
    metadata_status as _metadata_status,
)
from .orbis_sce_metadata_support import (
    parse_relocation_table as _parse_table_streaming,
)
from .orbis_sce_metadata_support import (
    read_bounded as _read_bounded,
)
from .orbis_sce_metadata_support import (
    relative_file_offset as _relative_file_offset,
)
from .orbis_sce_metadata_support import (
    sce_segments as _sce_segments,
)
from .orbis_sce_metadata_support import (
    segment_from_dict as _segment_from_dict,
)
from .orbis_sce_metadata_support import (
    sha256_file as _sha256_file,
)
from .orbis_sce_metadata_support import (
    string_at as _string_at,
)
from .orbis_sce_metadata_support import (
    table_from_dict as _table_from_dict,
)
from .orbis_sdk_definitions import (
    PT_SCE_DYNLIBDATA,
    RELA_ENTRY_SIZE,
    SCE_DYNAMIC_TAG_NAMES,
)


@dataclass(frozen=True, slots=True)
class SceMetadataReadResult:
    """Structured SCE metadata plus only the method-relevant entries."""

    status: str
    dynamic_tags: tuple[OrbisDynamicTag, ...] = ()
    sce_segments: tuple[OrbisSceSegment, ...] = ()
    relocation_tables: tuple[OrbisRelocationTable, ...] = ()
    relocation_entries: tuple[OrbisRelocationEntry, ...] = ()
    cache_path: str | None = None
    cache_sha256: str | None = None
    cache_entry_count: int | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ParsedMetadata:
    result: SceMetadataReadResult


class OrbisSceMetadataReader:
    """Read SCE dynamic tags and RELA records without applying relocations."""

    def read(
        self,
        elf_path: Path,
        *,
        source_sha256: str,
        tool: OrbisToolIdentity,
        cache_dir: Path,
        sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None,
        relevant_ranges: Iterable[tuple[int, int]] = (),
    ) -> SceMetadataReadResult:
        """Return source-bound metadata and stream the complete table to JSONL."""
        ranges = tuple(relevant_ranges)
        cache_key = _cache_key(source_sha256, tool, sdk_definition_identity)
        cache_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = cache_dir / f"sce-relocations-{cache_key[:20]}.jsonl"
        metadata_path = cache_dir / f"sce-relocations-{cache_key[:20]}.json"
        cached = self._load_cached(
            metadata_path,
            jsonl_path,
            cache_key,
            source_sha256,
            tool,
            sdk_definition_identity,
            ranges,
        )
        if cached is not None:
            return cached
        try:
            parsed, selected_entries, entry_count, cache_sha256 = self._parse_and_write(
                elf_path, ranges, jsonl_path
            )
        except (ELFError, OSError, RuntimeError, TypeError, ValueError) as error:
            return SceMetadataReadResult(
                status="malformed",
                diagnostics=(f"SCE metadata parsing failed: {error}",),
            )
        result = SceMetadataReadResult(
            status=parsed.result.status,
            dynamic_tags=parsed.result.dynamic_tags,
            sce_segments=parsed.result.sce_segments,
            relocation_tables=parsed.result.relocation_tables,
            relocation_entries=selected_entries,
            cache_path=str(jsonl_path),
            cache_sha256=cache_sha256,
            cache_entry_count=entry_count,
            diagnostics=parsed.result.diagnostics,
        )
        self._write_metadata(
            metadata_path,
            {
                "schema_version": SCE_METADATA_PARSER_VERSION,
                "cache_key": cache_key,
                "source_sha256": source_sha256,
                "tool_identity": asdict(tool),
                "sdk_definition_identity": (
                    asdict(sdk_definition_identity) if sdk_definition_identity is not None else None
                ),
                "entries": jsonl_path.name,
                "entries_sha256": cache_sha256,
                "entry_count": entry_count,
                "status": result.status,
                "dynamic_tags": [asdict(item) for item in result.dynamic_tags],
                "sce_segments": [asdict(item) for item in result.sce_segments],
                "relocation_tables": [asdict(item) for item in result.relocation_tables],
                "diagnostics": list(result.diagnostics),
            },
        )
        return result

    def _parse(
        self,
        elf_path: Path,
        relevant_ranges: tuple[tuple[int, int], ...],
        on_entry: Callable[[OrbisRelocationEntry], None],
    ) -> _ParsedMetadata:
        del relevant_ranges
        return _parse_elf(elf_path, on_entry)

    @staticmethod
    def _parse_and_write(
        elf_path: Path,
        relevant_ranges: tuple[tuple[int, int], ...],
        jsonl_path: Path,
    ) -> tuple[_ParsedMetadata, tuple[OrbisRelocationEntry, ...], int, str]:
        selected: list[OrbisRelocationEntry] = []
        entry_count = 0
        temporary: Path | None = None

        def emit(entry: OrbisRelocationEntry) -> None:
            nonlocal entry_count
            output.write(json.dumps(asdict(entry), sort_keys=True, separators=(",", ":")))
            output.write("\n")
            entry_count += 1
            if _in_ranges(entry.offset, relevant_ranges):
                selected.append(entry)

        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{jsonl_path.name}.",
                suffix=".tmp",
                dir=jsonl_path.parent,
                delete=False,
            ) as output:
                temporary = Path(output.name)
                parsed = OrbisSceMetadataReader()._parse(elf_path, relevant_ranges, emit)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(jsonl_path)
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        return parsed, tuple(selected), entry_count, _sha256_file(jsonl_path)

    @staticmethod
    def _write_metadata(path: Path, value: dict[str, object]) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as output:
                temporary = Path(output.name)
                json.dump(value, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(path)
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _load_cached(
        metadata_path: Path,
        jsonl_path: Path,
        cache_key: str,
        source_sha256: str,
        tool: OrbisToolIdentity,
        sdk_definition_identity: OrbisSdkDefinitionIdentity | None,
        relevant_ranges: tuple[tuple[int, int], ...],
    ) -> SceMetadataReadResult | None:
        if not metadata_path.is_file() or not jsonl_path.is_file():
            return None
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not _cache_metadata_matches(
                value,
                cache_key,
                source_sha256,
                tool,
                sdk_definition_identity,
                jsonl_path,
            ):
                return None
            selected_entries, entry_count = _read_cached_entries(jsonl_path, relevant_ranges)
            if entry_count != int(value["entry_count"]):
                return None
            return _cached_result(value, jsonl_path, selected_entries)
        except OSError, TypeError, ValueError, KeyError, json.JSONDecodeError:
            return None


def _cache_metadata_matches(
    value: object,
    cache_key: str,
    source_sha256: str,
    tool: OrbisToolIdentity,
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None,
    jsonl_path: Path,
) -> bool:
    if not isinstance(value, dict):
        return False
    expected_sdk_identity = (
        asdict(sdk_definition_identity) if sdk_definition_identity is not None else None
    )
    stored_sdk_identity = value.get("sdk_definition_identity")
    return all(
        (
            value.get("schema_version") == SCE_METADATA_PARSER_VERSION,
            value.get("cache_key") == cache_key,
            value.get("source_sha256") == source_sha256,
            value.get("tool_identity") == asdict(tool),
            _json_equivalent(stored_sdk_identity, expected_sdk_identity),
            value.get("entries_sha256") == _sha256_file(jsonl_path),
        )
    )


def _json_equivalent(left: object, right: object) -> bool:
    """Compare JSON-persisted values without tuple/list representation drift."""
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def _read_cached_entries(
    jsonl_path: Path, relevant_ranges: tuple[tuple[int, int], ...]
) -> tuple[list[OrbisRelocationEntry], int]:
    selected: list[OrbisRelocationEntry] = []
    count = 0
    with jsonl_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            count += 1
            entry = _entry_from_dict(json.loads(line))
            if _in_ranges(entry.offset, relevant_ranges):
                selected.append(entry)
    return selected, count


def _cached_result(
    value: dict[str, object],
    jsonl_path: Path,
    selected_entries: list[OrbisRelocationEntry],
) -> SceMetadataReadResult:
    return SceMetadataReadResult(
        status=str(value["status"]),
        dynamic_tags=tuple(
            _dynamic_tag_from_dict(cast(dict[str, object], item))
            for item in _json_list(value.get("dynamic_tags"))
        ),
        sce_segments=tuple(
            _segment_from_dict(cast(dict[str, object], item))
            for item in _json_list(value.get("sce_segments"))
        ),
        relocation_tables=tuple(
            _table_from_dict(cast(dict[str, object], item))
            for item in _json_list(value.get("relocation_tables"))
        ),
        relocation_entries=tuple(selected_entries),
        cache_path=str(jsonl_path),
        cache_sha256=str(value["entries_sha256"]),
        cache_entry_count=_json_int(value.get("entry_count")),
        diagnostics=tuple(str(item) for item in _json_list(value.get("diagnostics"))),
    )


def _parse_elf(
    elf_path: Path,
    on_entry: Callable[[OrbisRelocationEntry], None],
) -> _ParsedMetadata:
    patch_pyelftools_for_ps4()
    with elf_path.open("rb") as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 64:
            raise ValueError(f"SCE relocation reader requires ELF64, got ELF{elf.elfclass}")
        segments = tuple(_sce_segments(elf))
        dynlib = next((item for item in segments if item.type_code == PT_SCE_DYNLIBDATA), None)
        dynamic_section = elf.get_section_by_name(".dynamic")
        if dynlib is None or dynamic_section is None:
            return _missing_metadata(segments)
        endian = "<" if elf.little_endian else ">"
        return _parse_dynamic_metadata(
            stream,
            _file_size(stream),
            endian,
            segments,
            dynlib,
            dynamic_section,
            on_entry,
        )


def _missing_metadata(segments: tuple[_Segment, ...]) -> _ParsedMetadata:
    return _ParsedMetadata(
        SceMetadataReadResult(
            status="not_observed",
            sce_segments=tuple(item.model() for item in segments),
            diagnostics=("PT_SCE_DYNLIBDATA or .dynamic is absent",),
        )
    )


def _parse_dynamic_metadata(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    segments: tuple[_Segment, ...],
    dynlib: _Segment,
    dynamic_section: Any,
    on_entry: Callable[[OrbisRelocationEntry], None],
) -> _ParsedMetadata:
    dynamic_offset = dynamic_section["sh_offset"]
    dynamic_size = dynamic_section["sh_size"]
    tags = _dynamic_tags(_read_bounded(stream, dynamic_offset, dynamic_size, file_size), endian)
    values = _last_tag_values(tags)
    symbols = _read_dynamic_symbols(stream, file_size, endian, dynlib, values)
    tables, diagnostics = _parse_tables(
        stream, file_size, endian, dynlib, values, symbols, on_entry
    )
    return _ParsedMetadata(
        SceMetadataReadResult(
            status="partial" if diagnostics else _metadata_status(tables),
            dynamic_tags=tuple(
                OrbisDynamicTag(tag, SCE_DYNAMIC_TAG_NAMES.get(tag), value) for tag, value in tags
            ),
            sce_segments=tuple(item.model() for item in segments),
            relocation_tables=tuple(tables),
            diagnostics=tuple(diagnostics),
        )
    )


def _parse_tables(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    dynlib: _Segment,
    values: dict[str, int],
    symbols: dict[int, str | None],
    on_entry: Callable[[OrbisRelocationEntry], None],
) -> tuple[list[OrbisRelocationTable], list[str]]:
    tables: list[OrbisRelocationTable] = []
    diagnostics = _plt_rel_diagnostics(values)
    for table_name, address_tag, size_tag in (
        ("rela", "DT_SCE_RELA", "DT_SCE_RELASZ"),
        ("jmprel", "DT_SCE_JMPREL", "DT_SCE_PLTRELSZ"),
    ):
        table = _parse_table_streaming(
            stream,
            file_size,
            endian,
            dynlib,
            values,
            table_name,
            address_tag,
            size_tag,
            symbols,
            on_entry,
        )
        tables.append(table)
        diagnostics.extend(table.diagnostics)
    return tables, diagnostics


def _parse_table(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    dynlib: _Segment,
    values: dict[str, int],
    table_name: str,
    address_tag: str,
    size_tag: str,
    symbols: dict[int, str | None],
) -> tuple[OrbisRelocationTable, tuple[OrbisRelocationEntry, ...]]:
    """Compatibility view for focused parser tests and older callers.

    Production reads stream entries directly into the cache.  This wrapper
    retains the small tuple-shaped helper used by the existing unit tests.
    """
    entries: list[OrbisRelocationEntry] = []
    table = _parse_table_streaming(
        stream,
        file_size,
        endian,
        dynlib,
        values,
        table_name,
        address_tag,
        size_tag,
        symbols,
        entries.append,
    )
    return table, tuple(entries)


def _plt_rel_diagnostics(values: dict[str, int]) -> list[str]:
    value = values.get("DT_SCE_PLTREL")
    if value is None or value == 7:
        return []
    return [f"DT_SCE_PLTREL={value} is not the ELF64 RELA code 7"]


def _dynamic_tags(data: bytes, endian: str) -> tuple[tuple[int, int], ...]:
    unpack = struct.Struct(f"{endian}QQ")
    if len(data) % unpack.size:
        raise ValueError(".dynamic size is not aligned to ELF64 dynamic entries")
    result: list[tuple[int, int]] = []
    for offset in range(0, len(data), unpack.size):
        tag, value = unpack.unpack_from(data, offset)
        if tag == 0:
            break
        result.append((tag, value))
    return tuple(result)


def _last_tag_values(tags: tuple[tuple[int, int], ...]) -> dict[str, int]:
    return {
        name: value for tag, value in tags if (name := SCE_DYNAMIC_TAG_NAMES.get(tag)) is not None
    }


def _read_dynamic_symbols(
    stream: BinaryIO,
    file_size: int,
    endian: str,
    dynlib: _Segment,
    values: dict[str, int],
) -> dict[int, str | None]:
    address = values.get("DT_SCE_SYMTAB")
    size = values.get("DT_SCE_SYMTABSZ")
    entry_size = values.get("DT_SCE_SYMENT", RELA_ENTRY_SIZE)
    string_address = values.get("DT_SCE_STRTAB")
    string_size = values.get("DT_SCE_STRSZ", 0)
    if address is None or size is None or string_address is None or entry_size != 24:
        return {}
    symbol_offset = _relative_file_offset(dynlib, address, size, file_size)
    string_offset = _relative_file_offset(dynlib, string_address, string_size, file_size)
    if symbol_offset is None or string_offset is None or size % entry_size:
        return {}
    strings = _read_bounded(stream, string_offset, string_size, file_size)
    data = _read_bounded(stream, symbol_offset, size, file_size)
    unpack = struct.Struct(f"{endian}IBBHQQ")
    result: dict[int, str | None] = {}
    for index in range(size // entry_size):
        name_offset = unpack.unpack_from(data, index * entry_size)[0]
        result[index] = _string_at(strings, name_offset)
    return result


__all__ = ["OrbisSceMetadataReader", "SceMetadataReadResult"]

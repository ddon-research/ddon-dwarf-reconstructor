"""Focused tests for PS4/SCE dynamic metadata and RELA decoding."""

from __future__ import annotations

import hashlib
import io
import json
import struct
from dataclasses import asdict
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisToolIdentity
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump_profiles import (
    SCE_METADATA_PARSER_VERSION,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_sce_metadata import (
    _cache_metadata_matches,
    _dynamic_tags,
    _parse_table,
    _relative_file_offset,
    _Segment,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_sce_metadata_support import cache_key
from ddon_dwarf_reconstructor.infrastructure.orbis_sdk_definitions import sdk_definition_model


@pytest.mark.unit
@pytest.mark.functional
def test_dynamic_tags_preserve_vendor_values_and_names() -> None:
    data = struct.pack("<QQQQ", 0x6100002F, 0x20, 0x61000099, 0x1234)

    assert _dynamic_tags(data, "<") == (
        (0x6100002F, 0x20),
        (0x61000099, 0x1234),
    )


@pytest.mark.unit
@pytest.mark.functional
def test_sce_segment_relative_offset_accepts_zero_and_rejects_overflow() -> None:
    segment = _Segment("PT_SCE_DYNLIBDATA", 0x61000000, 0x100, 0, 0x80, 0)

    assert _relative_file_offset(segment, 0, 1, 0x200) == 0x100
    assert _relative_file_offset(segment, 0x7F, 1, 0x200) == 0x17F
    assert _relative_file_offset(segment, 0x80, 1, 0x200) is None


@pytest.mark.unit
@pytest.mark.functional
def test_rela_parser_decodes_signed_addend_orbis_code_and_symbol() -> None:
    payload = bytearray(0x200)
    struct.pack_into("<QQq", payload, 0x110, 0, (1 << 32) | 0x28, -4)
    table, entries = _parse_table(
        io.BytesIO(payload),
        len(payload),
        "<",
        _Segment("PT_SCE_DYNLIBDATA", 0x61000000, 0x100, 0, 0x80, 0),
        {
            "DT_SCE_RELA": 0x10,
            "DT_SCE_RELASZ": 24,
            "DT_SCE_RELAENT": 24,
        },
        "rela",
        "DT_SCE_RELA",
        "DT_SCE_RELASZ",
        {1: "external_method"},
    )

    assert table.status == "observed"
    assert table.file_offset == 0x110
    assert entries[0].relocation_id == "rela-00000000"
    assert entries[0].offset == 0
    assert entries[0].addend == -4
    assert entries[0].relocation_code == 0x28
    assert entries[0].relocation_name == "R_X86_64_ORBIS_GOTPCREL_LOAD"
    assert entries[0].symbol_name == "external_method"
    assert entries[0].resolution_status == "resolved"


@pytest.mark.unit
@pytest.mark.functional
def test_rela_parser_retains_unknown_code_and_truncation() -> None:
    payload = bytearray(0x120)
    struct.pack_into("<QQq", payload, 0x100, 0x20, (2 << 32) | 0x99, 8)
    table, entries = _parse_table(
        io.BytesIO(payload),
        len(payload),
        "<",
        _Segment("PT_SCE_DYNLIBDATA", 0x61000000, 0x100, 0, 0x40, 0),
        {
            "DT_SCE_RELA": 0,
            "DT_SCE_RELASZ": 25,
            "DT_SCE_RELAENT": 24,
        },
        "rela",
        "DT_SCE_RELA",
        "DT_SCE_RELASZ",
        {},
    )

    assert table.status == "partial"
    assert entries[0].resolution_status == "unknown_code"
    assert entries[0].symbol_name is None
    assert entries[0].offset == 0x20
    assert "size 25 is not divisible by entry size 24" in table.diagnostics[0]


@pytest.mark.unit
@pytest.mark.functional
def test_rela_parser_marks_file_boundary_overflow_malformed() -> None:
    table, entries = _parse_table(
        io.BytesIO(b"\0" * 0x210),
        0x210,
        "<",
        _Segment("PT_SCE_DYNLIBDATA", 0x61000000, 0x200, 0, 0x40, 0),
        {
            "DT_SCE_RELA": 0,
            "DT_SCE_RELASZ": 24,
            "DT_SCE_RELAENT": 24,
        },
        "rela",
        "DT_SCE_RELA",
        "DT_SCE_RELASZ",
        {},
    )

    assert table.status == "malformed"
    assert "outside PT_SCE_DYNLIBDATA or the ELF file" in table.diagnostics[0]
    assert entries == ()


@pytest.mark.unit
@pytest.mark.functional
@pytest.mark.parametrize(
    ("missing", "diagnostic"),
    (
        ("DT_SCE_RELASZ", "rela missing DT_SCE_RELASZ"),
        ("DT_SCE_RELAENT", "rela missing DT_SCE_RELAENT"),
    ),
)
def test_rela_parser_rejects_incomplete_table_descriptor(missing: str, diagnostic: str) -> None:
    values = {
        "DT_SCE_RELA": 0x10,
        "DT_SCE_RELASZ": 24,
        "DT_SCE_RELAENT": 24,
    }
    values.pop(missing)

    table, entries = _parse_table(
        io.BytesIO(b"\0" * 0x200),
        0x200,
        "<",
        _Segment("PT_SCE_DYNLIBDATA", 0x61000000, 0x100, 0, 0x80, 0),
        values,
        "rela",
        "DT_SCE_RELA",
        "DT_SCE_RELASZ",
        {},
    )

    assert table.status == "malformed"
    assert table.diagnostics == (diagnostic,)
    assert entries == ()


@pytest.mark.unit
@pytest.mark.regression
def test_sce_cache_key_binds_the_sdk_definition_identity() -> None:
    tool = OrbisToolIdentity("tool", "version", "target")

    without_definitions = cache_key("a" * 64, tool)
    with_definitions = cache_key("a" * 64, tool, sdk_definition_model())

    assert with_definitions != without_definitions


@pytest.mark.unit
@pytest.mark.regression
def test_sce_cache_metadata_accepts_json_round_trip_sdk_identity(tmp_path: Path) -> None:
    tool = OrbisToolIdentity("tool", "version", "target")
    sdk_identity = sdk_definition_model()
    source_sha256 = "a" * 64
    cache_key_value = cache_key(source_sha256, tool, sdk_identity)
    jsonl_path = tmp_path / "entries.jsonl"
    jsonl_path.write_text('{"offset": 0}\n', encoding="utf-8")
    entries_sha256 = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    metadata = {
        "schema_version": SCE_METADATA_PARSER_VERSION,
        "cache_key": cache_key_value,
        "source_sha256": source_sha256,
        "tool_identity": asdict(tool),
        "sdk_definition_identity": json.loads(json.dumps(asdict(sdk_identity))),
        "entries_sha256": entries_sha256,
    }

    assert _cache_metadata_matches(
        metadata,
        cache_key_value,
        source_sha256,
        tool,
        sdk_identity,
        jsonl_path,
    )

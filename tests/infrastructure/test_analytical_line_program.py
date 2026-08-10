"""Tests for line-program reconstruction from analytical rows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.jsonl_store import StoreDwarfInfo
from ddon_dwarf_reconstructor.infrastructure.analytical.line_program import build_line_program
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_store import ParquetDwarfStore
from ddon_dwarf_reconstructor.infrastructure.analytical.semantic_emitter import DwarfSemanticEmitter

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _rows() -> list[dict[str, object]]:
    return [
        {
            "unit_offset": 0,
            "ordinal": 0,
            "program_offset": 128,
            "command": 1,
            "address": 16,
            "file_index": 2,
            "source_file": "base.h",
            "directory": "include",
            "line": 7,
            "column": 3,
            "details": {"is_extended": False, "args": []},
        },
        {
            "unit_offset": 0,
            "ordinal": 1,
            "program_offset": 128,
            "command": 2,
            "address": 32,
            "file_index": 1,
            "source_file": "main.cpp",
            "directory": "src",
            "line": 12,
            "column": 1,
            "details": {"is_extended": True, "args": []},
        },
    ]


def test_line_program_preserves_file_indexes_and_entries() -> None:
    program = build_line_program(_rows())

    assert program is not None
    assert [entry.name for entry in program.header.file_entry] == ["main.cpp", "base.h"]
    assert program.header.include_directory == ("include", "src")
    assert [entry.state.file for entry in program.get_entries()] == [2, 1]
    assert program.get_entries()[1].is_extended is True


def test_line_program_preserves_unreferenced_header_file_entries() -> None:
    rows = [
        {
            "unit_offset": 0,
            "ordinal": 0,
            "entry_kind": "directory",
            "directory_index": 1,
            "directory": "src",
        },
        {
            "unit_offset": 0,
            "ordinal": 0,
            "entry_kind": "file",
            "file_index": 1,
            "directory_index": 1,
            "source_file": "main.cpp",
            "directory": "src",
        },
        {
            "unit_offset": 0,
            "ordinal": 1,
            "entry_kind": "file",
            "file_index": 2,
            "directory_index": 1,
            "source_file": "unused.h",
            "directory": "src",
        },
        {
            "unit_offset": 0,
            "ordinal": 0,
            "entry_kind": "state",
            "file_index": 1,
            "source_file": "main.cpp",
            "directory": "src",
            "line": 12,
        },
    ]

    program = build_line_program(rows)

    assert program is not None
    assert [entry.name for entry in program.header.file_entry] == ["main.cpp", "unused.h"]
    assert program.header.file_entry[1].dir_index == 1
    assert program.header.include_directory == ("src",)
    assert len(program.get_entries()) == 1


def test_store_dwarf_info_exposes_reconstructed_line_program() -> None:
    class _Store:
        def line_program_for_unit(self, unit_offset: int):
            assert unit_offset == 0
            return build_line_program(_rows())

    program = StoreDwarfInfo(_Store()).line_program_for_CU(SimpleNamespace(cu_offset=0))

    assert [entry.name for entry in program.header.file_entry] == ["main.cpp", "base.h"]


def test_parquet_store_reconstructs_line_program_through_typed_rows() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._payload_rows = lambda filters: _rows() if filters["unit_offset"] == 0 else []

    program = store.line_program_for_unit(0)

    assert program is not None
    assert program.program_start_offset == 128


def test_semantic_emitter_writes_unreferenced_line_header_files() -> None:
    records: list[dict[str, object]] = []

    class _Writer:
        def write(self, record: dict[str, object]) -> None:
            records.append(record)

    class _Entry:
        state = SimpleNamespace(file=1, line=12, address=16)
        command = 1
        is_extended = False
        args = []

    program = SimpleNamespace(
        header=SimpleNamespace(
            include_directory=[b"src"],
            file_entry=[
                SimpleNamespace(name=b"main.cpp", dir_index=1),
                SimpleNamespace(name=b"unused.h", dir_index=1),
            ],
        ),
        program_start_offset=128,
        get_entries=lambda: (_Entry(),),
    )
    dwarf_info = SimpleNamespace(line_program_for_CU=lambda _cu: program)
    emitter = DwarfSemanticEmitter("source", _Writer(), dwarf_info)
    emitter.begin_unit(0)

    emitter.write_unit_side_tables(SimpleNamespace(cu_offset=0))

    line_records = [record for record in records if record["record_type"] == "line"]
    assert [record["entry_kind"] for record in line_records] == [
        "directory",
        "file",
        "file",
        "state",
    ]
    assert line_records[2]["source_file"] == "unused.h"

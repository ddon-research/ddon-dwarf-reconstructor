"""Materializer behavior for malformed but source-preserved DWARF units."""

# The fixture intentionally mirrors the pyelftools method names.
# ruff: noqa: N802

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.core.platform import ELFPlatform
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    QueryStatus,
)
from ddon_dwarf_reconstructor.infrastructure.analytical import DwarfMaterializer
from ddon_dwarf_reconstructor.infrastructure.analytical.session import load_analytical_store
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Die:
    offset = 0x10
    depth = 0
    tag = "DW_TAG_class_type"
    attributes: dict[str, Any] = {}
    has_children = False
    abbrev_code = 1

    def is_null(self) -> bool:
        return False


class _MalformedCompilationUnit:
    cu_offset = 0
    header = {"version": 4, "address_size": 8, "unit_length": 32}

    def iter_DIEs(self) -> Any:
        yield _Die()
        raise KeyError(2261)


class _DwarfInfo:
    def iter_CUs(self) -> list[_MalformedCompilationUnit]:
        return [_MalformedCompilationUnit()]


class _Section:
    name = ".debug_info"
    header = {"sh_offset": 0, "sh_size": 4}


class _Elf:
    def iter_sections(self) -> list[_Section]:
        return [_Section()]


class _Session:
    def __init__(self, source: Path) -> None:
        self.file_handle = source.open("rb")
        self.elf_file = _Elf()
        self.dwarf_info = _DwarfInfo()
        self.platform = ELFPlatform.PS4

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_args: object) -> None:
        self.file_handle.close()


def test_materializer_publishes_raw_diagnostic_and_continues_after_malformed_cu(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))

    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path),
    ):
        manifest = materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "store-root",
                write_jsonl=True,
                write_parquet=False,
            )
        )

    assert materializer.cu_passes == 1
    assert manifest.status == "partial"
    assert manifest.configuration["parse_error_count"] == 1
    assert manifest.configuration["dwarf_parse_status"] == "partial"
    assert materializer.last_manifest_path is not None
    records_path = materializer.last_manifest_path.parent / "records.jsonl"
    rows = [json.loads(line) for line in records_path.read_text().splitlines()]
    unit = next(row for row in rows if row["record_type"] == "unit")
    diagnostic = next(row for row in rows if row["record_type"] == "abbreviation")
    assert unit["parser_status"] == QueryStatus.PARTIAL.value
    assert unit["details"]["abbrev_code"] == 2261
    assert diagnostic["parser_status"] == QueryStatus.PARTIAL.value
    assert diagnostic["details"]["raw_section_preserved"] is True
    with pytest.raises(ValueError, match="partial DWARF parsing"):
        load_analytical_store(materializer.last_manifest_path)
    store = load_analytical_store(materializer.last_manifest_path, allow_incomplete=True)
    assert store.manifest.status == "partial"

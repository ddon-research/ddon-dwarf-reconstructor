"""Regression tests for flattened pyelftools DIE parent reconstruction."""

# pyelftools exposes this compatibility method with its historical casing.
# ruff: noqa: N802

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.unit_emitter import DwarfUnitEmitter

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Die:
    def __init__(
        self,
        tag: str | None,
        offset: int,
        *,
        has_children: bool = False,
        null: bool = False,
    ) -> None:
        self.tag = tag
        self.offset = offset
        self.has_children = has_children
        self.attributes: dict[str, object] = {}
        self.abbrev_code = 1
        self._null = null

    def is_null(self) -> bool:
        return self._null


class _CompilationUnit:
    cu_offset = 0
    header = {"unit_length": 32}

    def __init__(self, dies: list[_Die]) -> None:
        self._dies = dies

    def iter_DIEs(self) -> Iterable[_Die]:
        return self._dies


class _MalformedCompilationUnit(_CompilationUnit):
    def __init__(self) -> None:
        die = _Die("DW_TAG_formal_parameter", 0x120)
        die.size = 5
        super().__init__([die])
        self._dielist = [die]

    def iter_DIEs(self) -> Iterable[_Die]:
        yield from self._dies
        raise KeyError(2261)


class _CaptureWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write(self, record: dict[str, object]) -> None:
        self.records.append(record)


def test_parent_stack_pops_at_null_dies_and_restores_siblings(tmp_path: Path) -> None:
    dies = [
        _Die("DW_TAG_compile_unit", 0x10, has_children=True),
        _Die("DW_TAG_namespace", 0x20, has_children=True),
        _Die("DW_TAG_class_type", 0x30),
        _Die(None, 0x31, null=True),
        _Die("DW_TAG_variable", 0x40),
        _Die(None, 0x41, null=True),
        _Die("DW_TAG_compile_unit", 0x50),
    ]
    writer = _CaptureWriter()
    DwarfUnitEmitter("a" * 64, writer, tmp_path).write_unit(_CompilationUnit(dies))

    die_rows = [row for row in writer.records if row["record_type"] == "die"]
    assert [row["parent_offset"] for row in die_rows] == [None, 0x10, 0x20, 0x20, 0x10, 0x10, None]
    assert [row["depth"] for row in die_rows] == [0, 1, 2, 2, 1, 1, 0]


def test_malformed_abbreviation_is_emitted_as_partial_raw_diagnostic(tmp_path: Path) -> None:
    writer = _CaptureWriter()
    diagnostic = DwarfUnitEmitter("a" * 64, writer, tmp_path).write_unit(
        _MalformedCompilationUnit()
    )

    assert diagnostic is not None
    assert diagnostic["abbrev_code"] == 2261
    unit = next(row for row in writer.records if row["record_type"] == "unit")
    assert unit["parser_status"] == "partial"
    assert unit["details"] == diagnostic
    abbreviation = next(
        row
        for row in writer.records
        if row["record_type"] == "abbreviation" and row["parser_status"] == "partial"
    )
    assert abbreviation["record_offset"] == 0x125
    assert abbreviation["abbrev_code"] == 2261

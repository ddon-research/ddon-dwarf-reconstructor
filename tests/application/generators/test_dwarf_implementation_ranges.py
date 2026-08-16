"""Tests for explicit DWARF implementation-range decoding."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_implementation_ranges import (
    code_ranges_for_die,
)
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import CodeRange


class _Attribute:
    def __init__(self, value: object, form: str = "DW_FORM_data4") -> None:
        self.value = value
        self.form = form


class _Die:
    def __init__(self, attributes: dict[str, _Attribute]) -> None:
        self.offset = 0x200
        self.attributes = attributes


def _context(query_port: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(class_parser=SimpleNamespace(query_port=query_port))


@pytest.mark.unit
@pytest.mark.functional
def test_low_high_pc_supports_absolute_and_offset_high_pc_forms() -> None:
    context = _context()
    cu = SimpleNamespace()
    absolute = _Die(
        {
            "DW_AT_low_pc": _Attribute(0x1000, "DW_FORM_addr"),
            "DW_AT_high_pc": _Attribute(0x1020, "DW_FORM_addr"),
        }
    )
    offset = _Die(
        {
            "DW_AT_low_pc": _Attribute(0x2000, "DW_FORM_addr"),
            "DW_AT_high_pc": _Attribute(0x20),
        }
    )

    absolute_ranges, absolute_diagnostics = code_ranges_for_die(context, cu, absolute)
    offset_ranges, offset_diagnostics = code_ranges_for_die(context, cu, offset)

    assert (absolute_ranges[0].start_address, absolute_ranges[0].end_address) == (0x1000, 0x1020)
    assert (offset_ranges[0].start_address, offset_ranges[0].end_address) == (0x2000, 0x2020)
    assert absolute_diagnostics == offset_diagnostics == ()


@pytest.mark.unit
@pytest.mark.functional
def test_address_domain_rejects_sentinels_and_overflow() -> None:
    invalid = (
        (-(1), 0x10),
        (0, (1 << 64) - 1),
        (0, 1 << 64),
        ((1 << 64) - 2, (1 << 64) + 1),
    )

    for start, end in invalid:
        with pytest.raises(ValueError, match="64-bit address domain"):
            CodeRange(start, end, "fixture")


@pytest.mark.unit
@pytest.mark.functional
def test_overflowing_high_pc_is_rejected_before_target_planning() -> None:
    die = _Die(
        {
            "DW_AT_low_pc": _Attribute((1 << 64) - 2, "DW_FORM_addr"),
            "DW_AT_high_pc": _Attribute(4, "DW_FORM_data4"),
        }
    )

    ranges, diagnostics = code_ranges_for_die(_context(), SimpleNamespace(), die)

    assert ranges == ()
    assert diagnostics == ("DW_AT_low_pc/DW_AT_high_pc is not a valid range",)


@pytest.mark.unit
@pytest.mark.functional
def test_range_records_fail_closed_on_unknown_and_invalid_intervals() -> None:
    records = (
        "malformed",
        {"entry_kind": "base_address", "base_address": 0x1000},
        {"start_address": 0x10, "end_address": 0x20, "is_absolute": False},
        {"start_address": 0x30, "end_address": 0x20, "is_absolute": True},
        {"start_address": 0x40, "end_address": 0x50, "is_absolute": None},
        {"parser_status": QueryStatus.PARTIAL.value},
    )
    query_port = SimpleNamespace(
        find_code_ranges=lambda _offset: QueryResult(QueryStatus.PARTIAL, records)
    )
    die = _Die({"DW_AT_ranges": _Attribute(0x40)})

    ranges, diagnostics = code_ranges_for_die(_context(query_port), SimpleNamespace(), die)

    assert [(item.start_address, item.end_address) for item in ranges] == [(0x1010, 0x1020)]
    assert "range absolute-ness is unknown" in diagnostics
    assert "materialized range is not a valid interval" in diagnostics
    assert "range record is partial" in diagnostics


@pytest.mark.unit
@pytest.mark.functional
def test_relative_materialized_range_without_base_is_not_used() -> None:
    query_port = SimpleNamespace(
        find_code_ranges=lambda _offset: QueryResult(
            QueryStatus.COMPLETE,
            ({"start_address": 0x10, "end_address": 0x20, "is_absolute": False},),
        )
    )

    ranges, diagnostics = code_ranges_for_die(
        _context(query_port), SimpleNamespace(), _Die({"DW_AT_ranges": _Attribute(0x40)})
    )

    assert ranges == ()
    assert diagnostics == ("relative range has no base address",)


@pytest.mark.unit
@pytest.mark.functional
def test_raw_range_list_decoding_handles_base_relative_and_invalid_entries() -> None:
    entries = (
        SimpleNamespace(base_address=0x3000, begin_offset=None, end_offset=None, is_absolute=None),
        SimpleNamespace(base_address=None, begin_offset=None, end_offset=None, is_absolute=None),
        SimpleNamespace(base_address=None, begin_offset=0x10, end_offset=0x20, is_absolute=False),
        SimpleNamespace(base_address=None, begin_offset=0x30, end_offset=0x40, is_absolute=True),
        SimpleNamespace(base_address=None, begin_offset=0x50, end_offset=0x40, is_absolute=True),
        SimpleNamespace(base_address=None, begin_offset=0x60, end_offset=0x70, is_absolute=None),
    )

    class _RangeLists:
        def get_range_list_at_offset(self, _offset: int, *, cu: object) -> tuple[object, ...]:
            del cu
            return entries

    cu = SimpleNamespace(dwarfinfo=SimpleNamespace(range_lists=lambda: _RangeLists()))
    die = _Die({"DW_AT_ranges": _Attribute(0x40)})

    ranges, diagnostics = code_ranges_for_die(_context(), cu, die)

    assert [(item.start_address, item.end_address) for item in ranges] == [
        (0x3010, 0x3020),
        (0x30, 0x40),
    ]
    assert "range absolute-ness is unknown" in diagnostics
    assert "DW_AT_ranges entry is not a valid interval" in diagnostics


@pytest.mark.unit
@pytest.mark.functional
def test_raw_range_list_adapter_unavailable_and_decode_failure_are_diagnostics() -> None:
    die = _Die({"DW_AT_ranges": _Attribute(0x40)})
    unavailable_ranges, unavailable_diagnostics = code_ranges_for_die(
        _context(), SimpleNamespace(), die
    )

    class _FailingRangeLists:
        def get_range_list_at_offset(self, _offset: int, *, cu: object) -> tuple[object, ...]:
            del cu
            raise RuntimeError("bad range list")

    failing_cu = SimpleNamespace(
        dwarfinfo=SimpleNamespace(range_lists=lambda: _FailingRangeLists())
    )
    failed_ranges, failed_diagnostics = code_ranges_for_die(_context(), failing_cu, die)

    assert unavailable_ranges == failed_ranges == ()
    assert unavailable_diagnostics == ("DW_AT_ranges list adapter is unavailable",)
    assert "DW_AT_ranges could not be decoded: bad range list" in failed_diagnostics

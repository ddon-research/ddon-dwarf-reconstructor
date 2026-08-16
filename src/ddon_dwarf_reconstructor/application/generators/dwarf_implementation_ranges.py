"""DWARF code-range decoding for implementation candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.models.implementation_evidence import CodeRange
from ..generation.runtime import GenerationRuntime


def code_ranges_for_die(
    context: GenerationRuntime,
    cu: DwarfCompilationUnit,
    die: DwarfEntry,
) -> tuple[tuple[CodeRange, ...], tuple[str, ...]]:
    """Decode only ranges whose address semantics are explicit and valid."""
    attributes = die.attributes
    if "DW_AT_low_pc" in attributes and "DW_AT_high_pc" in attributes:
        low = _integer_attribute(attributes["DW_AT_low_pc"])
        high = _high_pc(attributes["DW_AT_high_pc"], low)
        if low is not None and high is not None:
            try:
                return (CodeRange(low, high, "DW_AT_low_pc/DW_AT_high_pc"),), ()
            except ValueError:
                return (), ("DW_AT_low_pc/DW_AT_high_pc is not a valid range",)
    if "DW_AT_ranges" not in attributes:
        return (), ("implementation DIE has no supported code range",)
    query_port = context.class_parser.query_port
    if query_port is not None:
        return _ranges_from_records(query_port.find_code_ranges(die.offset))
    return _ranges_from_raw_list(cu, die)


def _ranges_from_records(query: QueryResult) -> tuple[tuple[CodeRange, ...], tuple[str, ...]]:
    base: int | None = None
    ranges: list[CodeRange] = []
    diagnostics: list[str] = []
    if query.status is not QueryStatus.COMPLETE:
        diagnostics.append(f"materialized range query was {query.status.value}")
    for record in query.items:
        base, code_range, record_diagnostics = _materialized_range(record, base)
        diagnostics.extend(record_diagnostics)
        if code_range is not None:
            ranges.append(code_range)
    return tuple(ranges), tuple(dict.fromkeys(diagnostics))


def _materialized_range(
    record: object, base: int | None
) -> tuple[int | None, CodeRange | None, tuple[str, ...]]:
    if not isinstance(record, Mapping):
        return base, None, ()
    diagnostics = list(_range_record_diagnostics(record))
    is_base, next_base = _materialized_base(record, base)
    if is_base:
        return next_base, None, tuple(diagnostics)
    start, end = _materialized_coordinates(record)
    if start is None or end is None:
        return base, None, tuple(diagnostics)
    return _materialized_interval(start, end, record.get("is_absolute"), base, diagnostics)


def _range_record_diagnostics(record: Mapping[str, object]) -> tuple[str, ...]:
    parser_status = record.get("parser_status")
    if parser_status not in (None, QueryStatus.COMPLETE.value):
        return (f"range record is {parser_status}",)
    return ()


def _materialized_base(record: Mapping[str, object], base: int | None) -> tuple[bool, int | None]:
    candidate_base = _integer_value(record.get("base_address"))
    if record.get("entry_kind") == "base_address" or candidate_base is not None:
        return True, candidate_base if candidate_base is not None else base
    return False, base


def _materialized_coordinates(record: Mapping[str, object]) -> tuple[int | None, int | None]:
    return (
        _integer_value(record.get("start_address")),
        _integer_value(record.get("end_address")),
    )


def _materialized_interval(
    start: int,
    end: int,
    is_absolute: object,
    base: int | None,
    diagnostics: list[str],
) -> tuple[int | None, CodeRange | None, tuple[str, ...]]:
    if is_absolute not in (True, False):
        diagnostics.append("range absolute-ness is unknown")
        return base, None, tuple(diagnostics)
    if is_absolute is False:
        if base is None:
            diagnostics.append("relative range has no base address")
            return base, None, tuple(diagnostics)
        start += base
        end += base
    try:
        return base, CodeRange(start, end, "DW_AT_ranges"), tuple(diagnostics)
    except ValueError:
        diagnostics.append("materialized range is not a valid interval")
        return base, None, tuple(diagnostics)


def _ranges_from_raw_list(
    cu: DwarfCompilationUnit, die: DwarfEntry
) -> tuple[tuple[CodeRange, ...], tuple[str, ...]]:
    range_lists_factory = getattr(getattr(cu, "dwarfinfo", None), "range_lists", None)
    attribute = die.attributes.get("DW_AT_ranges")
    raw = _integer_attribute(attribute) if attribute is not None else None
    if not callable(range_lists_factory) or raw is None:
        return (), ("DW_AT_ranges list adapter is unavailable",)
    try:
        entries = cast(Any, range_lists_factory()).get_range_list_at_offset(raw, cu=cu)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        return (), (f"DW_AT_ranges could not be decoded: {error}",)
    base: int | None = _integer_attribute(die.attributes.get("DW_AT_low_pc"))
    ranges: list[CodeRange] = []
    diagnostics: list[str] = []
    for entry in entries:
        base, code_range, entry_diagnostics = _raw_range_entry(entry, base)
        if code_range is not None:
            ranges.append(code_range)
        diagnostics.extend(entry_diagnostics)
    return tuple(ranges), tuple(dict.fromkeys(diagnostics))


def _raw_range_entry(
    entry: object, base: int | None
) -> tuple[int | None, CodeRange | None, tuple[str, ...]]:
    entry_base = _integer_value(getattr(entry, "base_address", None))
    if entry_base is not None:
        return entry_base, None, ()
    start = _integer_value(getattr(entry, "begin_offset", None))
    end = _integer_value(getattr(entry, "end_offset", None))
    if start is None or end is None:
        return base, None, ()
    is_absolute = getattr(entry, "is_absolute", None)
    if is_absolute not in (True, False):
        return base, None, ("range absolute-ness is unknown",)
    if is_absolute is False:
        if base is None:
            return base, None, ("relative DW_AT_ranges entry has no base address",)
        start += base
        end += base
    try:
        return base, CodeRange(start, end, "DW_AT_ranges"), ()
    except ValueError:
        return base, None, ("DW_AT_ranges entry is not a valid interval",)


def _high_pc(attribute: object, low: int | None) -> int | None:
    high = _integer_attribute(attribute)
    if high is None:
        return None
    form = str(getattr(attribute, "form", ""))
    if "addr" in form:
        return high
    return low + high if low is not None else None


def _integer_attribute(attribute: object | None) -> int | None:
    return _integer_value(getattr(attribute, "value", None)) if attribute is not None else None


def _integer_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["code_ranges_for_die"]

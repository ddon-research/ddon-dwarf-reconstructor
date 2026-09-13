"""Source/CU/DIE key handling for the bounded method-context projection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus

type DieKey = tuple[int, int]
type RequestedDieKey = tuple[int | None, int]


def row_key(row: Mapping[str, Any]) -> DieKey | None:
    """Read a source/CU-qualified DIE key from one analytical row."""
    unit_offset = as_int(row.get("unit_offset"))
    die_offset = as_int(row.get("die_offset"))
    return (unit_offset, die_offset) if unit_offset is not None and die_offset is not None else None


def row_keys(rows: Sequence[Mapping[str, Any]]) -> tuple[DieKey, ...]:
    """Return unique source/CU-qualified keys in stable row order."""
    return tuple(dict.fromkeys(key for row in rows if (key := row_key(row)) is not None))


def known_units(keys: Sequence[RequestedDieKey]) -> tuple[int, ...]:
    """Return known CU offsets from a request key sequence."""
    return tuple(sorted({unit for unit, _offset in keys if unit is not None}))


def has_unknown_units(keys: Sequence[RequestedDieKey]) -> bool:
    """Return whether any requested DIE lacks CU provenance."""
    return any(unit is None for unit, _offset in keys)


def unit_filter(keys: Sequence[RequestedDieKey | DieKey]) -> dict[str, object]:
    """Build a safe CU predicate only when every key is source-bound."""
    if any(unit is None for unit, _offset in keys):
        return {}
    units = tuple(sorted({unit for unit, _offset in keys if unit is not None}))
    return {"unit_offset": units} if units else {}


def filter_rows_by_keys(
    rows: Sequence[Mapping[str, Any]],
    requested_keys: Sequence[RequestedDieKey | DieKey],
) -> tuple[dict[str, Any], ...]:
    """Retain rows matching exact bound keys or explicitly unknown offsets."""
    exact = {(unit, offset) for unit, offset in requested_keys if unit is not None}
    unknown_offsets = {offset for unit, offset in requested_keys if unit is None}
    return tuple(
        dict(row)
        for row in rows
        if ((key := row_key(row)) is not None and (key in exact or key[1] in unknown_offsets))
    )


def filter_parent_rows(
    rows: Sequence[Mapping[str, Any]],
    requested_keys: Sequence[RequestedDieKey | DieKey],
) -> tuple[dict[str, Any], ...]:
    """Retain formal-parameter rows whose source-bound parent was requested."""
    exact = {(unit, offset) for unit, offset in requested_keys if unit is not None}
    unknown_offsets = {offset for unit, offset in requested_keys if unit is None}
    return tuple(
        dict(row)
        for row in rows
        if (
            (unit := as_int(row.get("unit_offset"))) is not None
            and (parent := as_int(row.get("parent_offset"))) is not None
            and ((unit, parent) in exact or parent in unknown_offsets)
        )
    )


def resolve_requested_keys(
    requested: Sequence[RequestedDieKey],
    method_rows: Sequence[Mapping[str, Any]],
) -> tuple[DieKey, ...] | None:
    """Resolve legacy bare offsets only when one CU is observed for each."""
    available: dict[int, set[int]] = defaultdict(set)
    for row in method_rows:
        key = row_key(row)
        if key is not None:
            available[key[1]].add(key[0])
    resolved: list[DieKey] = []
    for unit, offset in requested:
        if unit is not None:
            resolved.append((unit, offset))
            continue
        units = available.get(offset, set())
        if len(units) > 1:
            return None
        if units:
            resolved.append((next(iter(units)), offset))
    return tuple(dict.fromkeys(resolved))


def reference_target_keys(rows: Sequence[Mapping[str, Any]]) -> tuple[DieKey, ...]:
    """Resolve reference targets within their source CU context."""
    result: list[DieKey] = []
    for row in rows:
        unit_offset = as_int(row.get("unit_offset"))
        target = as_int(row.get("target_offset"))
        if unit_offset is not None and target is not None:
            result.append((unit_offset, target))
    return tuple(dict.fromkeys(result))


def resolve_lookup_key(
    rows: Mapping[DieKey, Any], die_offset: int, unit_offset: int | None
) -> DieKey | None:
    """Resolve one view lookup, refusing ambiguous bare offsets."""
    if unit_offset is not None:
        return (unit_offset, die_offset)
    matches = tuple(key for key in rows if key[1] == die_offset)
    return matches[0] if len(matches) == 1 else None


def lookup_is_ambiguous(rows: Mapping[DieKey, Any], die_offset: int) -> bool:
    """Return whether a bare DIE offset maps to more than one CU."""
    return sum(key[1] == die_offset for key in rows) > 1


def ambiguous_context_result(
    provenance: tuple[str, ...],
    keys: Sequence[RequestedDieKey],
) -> QueryResult:
    """Return fail-closed evidence for an unbound ambiguous request."""
    offsets = tuple(sorted({offset for unit, offset in keys if unit is None}))
    rendered = ", ".join(f"0x{offset:x}" for offset in offsets)
    return QueryResult(
        QueryStatus.UNAVAILABLE,
        provenance=provenance,
        diagnostics=(
            "method context request lacks CU provenance for ambiguous DIE offset(s): " + rendered,
        ),
    )


def read_context_artifacts(
    store: Any,
    die_rows: Sequence[Mapping[str, Any]],
    context_keys: Sequence[DieKey],
    context_offsets: tuple[int, ...],
    attribute_columns: Sequence[str],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Read and source-bind attributes and locations for one context batch."""
    die_keys = row_keys(die_rows)
    attributes = store._rows(
        "attribute",
        {"die_offset": _row_offsets(die_rows), **unit_filter(die_keys)},
        columns=attribute_columns,
        order_by=("unit_offset", "die_offset", "ordinal"),
        operation="validation_attributes",
    )
    locations = store._rows(
        "location",
        {"die_offset": context_offsets, **unit_filter(context_keys)},
        order_by=("unit_offset", "die_offset", "ordinal", "record_offset"),
        operation="validation_locations",
    )
    return filter_rows_by_keys(attributes, die_keys), filter_rows_by_keys(locations, context_keys)


def _row_offsets(rows: Sequence[Mapping[str, Any]]) -> tuple[int, ...]:
    """Return unique DIE offsets for a bounded family predicate."""
    return tuple(
        sorted({offset for row in rows if (offset := as_int(row.get("die_offset"))) is not None})
    )


def as_int(value: object) -> int | None:
    """Decode the integer forms returned by the Doris DB-API adapter."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, Decimal)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


__all__ = [
    "ambiguous_context_result",
    "as_int",
    "filter_parent_rows",
    "filter_rows_by_keys",
    "has_unknown_units",
    "known_units",
    "lookup_is_ambiguous",
    "read_context_artifacts",
    "reference_target_keys",
    "resolve_lookup_key",
    "resolve_requested_keys",
    "row_key",
    "row_keys",
    "unit_filter",
]

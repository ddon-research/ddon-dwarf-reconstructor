"""Bounded candidate hydration helpers for the Doris Flight benchmark."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from ...doris import DorisConfig
from .specs import ParameterizedQuery


def hydration_groups(
    candidates: tuple[tuple[Any, ...], ...], strategy: str, batch_size: int
) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    """Partition candidate usages without deduplicating their output positions."""
    if strategy == "n_plus_one":
        return tuple((candidate,) for candidate in candidates)
    return tuple(
        candidates[index : index + batch_size] for index in range(0, len(candidates), batch_size)
    )


def hydration_specs(
    config: DorisConfig,
    source_id: str,
    candidates: tuple[tuple[Any, ...], ...],
    placeholder: Literal["%s", "?"],
    family: Literal["die", "attribute"],
) -> tuple[ParameterizedQuery, ...]:
    """Build bounded DIE or attribute queries for a candidate group."""
    groups: dict[int, list[int]] = {}
    for row in candidates:
        if len(row) < 2 or not all(isinstance(value, int) for value in row[:2]):
            continue
        groups.setdefault(row[0], []).append(row[1])
    result: list[ParameterizedQuery] = []
    table = qualified_table(config, family)
    for unit_offset, die_offsets in groups.items():
        offsets = tuple(dict.fromkeys(die_offsets))
        if len(offsets) == 1:
            condition = f"die_offset = {placeholder}"
            params: tuple[object, ...] = (source_id, unit_offset, offsets[0])
        else:
            condition = f"die_offset IN ({', '.join(placeholder for _ in offsets)})"
            params = (source_id, unit_offset, *offsets)
        result.append(
            ParameterizedQuery(
                f"hydrate_{family}",
                f"SELECT * FROM {table} WHERE source_id = {placeholder} "
                f"AND unit_offset = {placeholder} AND {condition} "
                "ORDER BY die_offset, ordinal",
                params,
                {"unit_offset": unit_offset, "candidate_count": len(candidates)},
            )
        )
    return tuple(result)


def join_hydration(
    candidates: tuple[tuple[Any, ...], ...],
    die_rows: list[tuple[tuple[Any, ...], ...]],
    attr_rows: list[tuple[tuple[Any, ...], ...]],
) -> Iterable[tuple[int, tuple[tuple[Any, ...], ...], tuple[tuple[Any, ...], ...]]]:
    """Join fetched family rows back to every original candidate occurrence."""
    dies = _group_by_offset(die_rows)
    attributes = _group_by_offset(attr_rows)
    for index, candidate in enumerate(candidates):
        if len(candidate) < 2 or not all(isinstance(value, int) for value in candidate[:2]):
            continue
        key = (candidate[0], candidate[1])
        yield index, dies.get(key, ()), attributes.get(key, ())


def qualified_table(config: DorisConfig, family: str) -> str:
    """Return a validated family table identifier."""
    if not family or not all(character.isalnum() or character == "_" for character in family):
        raise ValueError(f"Unsafe Doris family: {family!r}")
    for value in (config.database, f"{config.table}_{family}"):
        if not value or not all(character.isalnum() or character == "_" for character in value):
            raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{config.database}`.`{config.table}_{family}`"


def _group_by_offset(
    groups: list[tuple[tuple[Any, ...], ...]],
) -> dict[tuple[int, int], tuple[tuple[Any, ...], ...]]:
    grouped: dict[tuple[int, int], list[tuple[Any, ...]]] = {}
    for rows in groups:
        for row in rows:
            if len(row) >= 2 and all(isinstance(value, int) for value in row[:2]):
                grouped.setdefault((row[0], row[1]), []).append(row)
    return {key: tuple(rows) for key, rows in grouped.items()}

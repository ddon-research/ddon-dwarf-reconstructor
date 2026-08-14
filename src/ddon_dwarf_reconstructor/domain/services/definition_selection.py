"""Canonical policy for ranking duplicate DWARF type definitions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

FORWARD_DECLARATION_SCORE = -1_000
INCOMPLETE_TYPE_SCORE = -500
TYPEDEF_SCORE = 5_000
ENUM_SCORE = 6_000
BASE_TYPE_SCORE = 8_000
CHILDREN_SCORE = 10_000
NESTED_ENUM_SCORE = 1_000
NESTED_STRUCT_SCORE = 500
NESTED_UNION_SCORE = 300


class TaggedChild(Protocol):
    """Minimum child shape needed for nested-type counting."""

    tag: str


@dataclass(frozen=True)
class NestedTypeCounts:
    """Counts of directly nested aggregate types."""

    enums: int = 0
    structs: int = 0
    unions: int = 0


@dataclass(frozen=True)
class DefinitionSignals:
    """Source-neutral evidence used to rank a type definition."""

    tag: str
    byte_size: int = 0
    has_children: bool = False
    is_declaration: bool = False
    has_type_reference: bool = False
    nested: NestedTypeCounts = NestedTypeCounts()


@dataclass(frozen=True)
class DefinitionCandidate:
    """A scored definition location shared by discovery and cache adapters."""

    symbol: str
    cu_offset: int
    die_offset: int
    score: int
    complete: bool
    byte_size: int = 0
    has_children: bool = False
    is_declaration: bool = False
    has_type_reference: bool = False


def count_nested_types(children: Iterable[TaggedChild]) -> NestedTypeCounts:
    """Count relevant direct children in one pass."""
    enums = structs = unions = 0
    for child in children:
        if child.tag == "DW_TAG_enumeration_type":
            enums += 1
        elif child.tag == "DW_TAG_structure_type":
            structs += 1
        elif child.tag == "DW_TAG_union_type":
            unions += 1
    return NestedTypeCounts(enums=enums, structs=structs, unions=unions)


def score_definition(signals: DefinitionSignals) -> int:
    """Return the canonical completeness score for available evidence."""
    if signals.is_declaration:
        return FORWARD_DECLARATION_SCORE
    if signals.tag == "DW_TAG_typedef":
        return TYPEDEF_SCORE if signals.has_type_reference else INCOMPLETE_TYPE_SCORE
    if signals.tag == "DW_TAG_base_type":
        return BASE_TYPE_SCORE
    if signals.tag == "DW_TAG_enumeration_type":
        return ENUM_SCORE if signals.byte_size > 0 else INCOMPLETE_TYPE_SCORE

    score = signals.byte_size
    if signals.has_children:
        score += CHILDREN_SCORE
    score += signals.nested.enums * NESTED_ENUM_SCORE
    score += signals.nested.structs * NESTED_STRUCT_SCORE
    score += signals.nested.unions * NESTED_UNION_SCORE
    return score


def build_definition_candidate(
    symbol: str,
    *,
    cu_offset: int,
    die_offset: int,
    signals: DefinitionSignals,
) -> DefinitionCandidate:
    """Build the canonical candidate shared by every lookup adapter.

    Keeping construction beside the scoring policy prevents storage adapters
    from quietly diverging in their interpretation of completeness.
    """
    score = score_definition(signals)
    return DefinitionCandidate(
        symbol=symbol,
        cu_offset=cu_offset,
        die_offset=die_offset,
        score=score,
        complete=not signals.is_declaration and score >= 0,
        byte_size=signals.byte_size,
        has_children=signals.has_children,
        is_declaration=signals.is_declaration,
        has_type_reference=signals.has_type_reference,
    )


def definition_candidate_sort_key(
    candidate: DefinitionCandidate, *, depth: int = 0
) -> tuple[int, int, int, int]:
    """Return the deterministic ordering shared by every storage adapter."""
    return (-candidate.score, candidate.cu_offset, candidate.die_offset, depth)


def is_early_exit_candidate(signals: DefinitionSignals, score: int) -> bool:
    """Return whether fast search can safely accept this candidate."""
    return (
        signals.has_children and signals.byte_size > 0 and not signals.is_declaration
    ) or score >= TYPEDEF_SCORE

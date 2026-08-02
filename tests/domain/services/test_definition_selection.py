"""Tests for the canonical DWARF definition-selection policy."""

from dataclasses import dataclass

import pytest

from ddon_dwarf_reconstructor.domain.services.definition_selection import (
    BASE_TYPE_SCORE,
    CHILDREN_SCORE,
    ENUM_SCORE,
    FORWARD_DECLARATION_SCORE,
    INCOMPLETE_TYPE_SCORE,
    NESTED_ENUM_SCORE,
    NESTED_STRUCT_SCORE,
    NESTED_UNION_SCORE,
    TYPEDEF_SCORE,
    DefinitionSignals,
    NestedTypeCounts,
    count_nested_types,
    is_early_exit_candidate,
    score_definition,
)


@dataclass(frozen=True)
class _Child:
    tag: str


@pytest.mark.unit
def test_type_specific_scores_are_canonical() -> None:
    assert score_definition(DefinitionSignals("DW_TAG_class_type", is_declaration=True)) == (
        FORWARD_DECLARATION_SCORE
    )
    assert score_definition(DefinitionSignals("DW_TAG_typedef", has_type_reference=True)) == (
        TYPEDEF_SCORE
    )
    assert score_definition(DefinitionSignals("DW_TAG_typedef")) == INCOMPLETE_TYPE_SCORE
    assert score_definition(DefinitionSignals("DW_TAG_base_type")) == BASE_TYPE_SCORE
    assert score_definition(DefinitionSignals("DW_TAG_enumeration_type", byte_size=4)) == (
        ENUM_SCORE
    )


@pytest.mark.unit
def test_aggregate_score_combines_all_available_evidence() -> None:
    signals = DefinitionSignals(
        "DW_TAG_class_type",
        byte_size=528,
        has_children=True,
        nested=NestedTypeCounts(enums=2, structs=1, unions=1),
    )

    assert score_definition(signals) == (
        528 + CHILDREN_SCORE + 2 * NESTED_ENUM_SCORE + NESTED_STRUCT_SCORE + NESTED_UNION_SCORE
    )
    assert is_early_exit_candidate(signals, score_definition(signals))


@pytest.mark.unit
def test_nested_types_are_counted_in_one_pass() -> None:
    children = iter(
        [
            _Child("DW_TAG_member"),
            _Child("DW_TAG_enumeration_type"),
            _Child("DW_TAG_structure_type"),
            _Child("DW_TAG_union_type"),
        ]
    )

    assert count_nested_types(children) == NestedTypeCounts(enums=1, structs=1, unions=1)


@pytest.mark.unit
def test_evidence_limited_layout_score_preserves_dump_ranking() -> None:
    signals = DefinitionSignals(
        "DW_TAG_class_type",
        byte_size=528,
        nested=NestedTypeCounts(enums=2, structs=1),
    )

    assert score_definition(signals) == 3_028
    assert not is_early_exit_candidate(signals, score_definition(signals))

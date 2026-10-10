"""Aggregate dispatch preserves alias and target identities separately."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.parsing.aggregate_target import (
    AggregateEvidenceError,
    resolve_aggregate_target,
)
from tests.support.type_graph import TypeDie, TypeUnit

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_alias_dispatch_preserves_target_cu_and_alias_identity_at_offset_zero() -> None:
    target = TypeDie("DW_TAG_class_type", 0, cu=TypeUnit(20)).named("cArcLoader<1>")
    alias = TypeDie("DW_TAG_typedef", 0, cu=TypeUnit(10)).named("cArcLoader01").link(target)
    resolver = LazyTypeResolver(Mock(), Mock())
    parser = ClassParser(resolver, Mock())
    info = parser.parse_class_info(alias.cu, alias)
    assert (info.name, info.cu_offset, info.die_offset) == ("cArcLoader<1>", 20, 0)
    assert len(info.source_aliases) == 1
    reference = info.source_aliases[0]
    assert (reference.name, reference.cu_offset, reference.die_offset) == ("cArcLoader01", 10, 0)
    assert reference.alias_target.name == "cArcLoader<1>"
    assert parser.parse_class_info(target.cu, target).source_aliases == ()


def test_alias_chain_retains_every_declared_alias() -> None:
    target = TypeDie("DW_TAG_structure_type", 1).named("Target")
    inner = TypeDie("DW_TAG_typedef", 2).named("Inner").link(target)
    outer = TypeDie("DW_TAG_typedef", 3).named("Outer").link(inner)
    result = resolve_aggregate_target(outer, LazyTypeResolver(Mock(), Mock()))
    assert result.die is target
    assert [alias.name for alias in result.aliases] == ["Outer", "Inner"]


@pytest.mark.parametrize("failure", ["missing", "cycle", "primitive", "pointer"])
def test_invalid_aggregate_evidence_cannot_produce_dummy_class(failure) -> None:
    alias = TypeDie("DW_TAG_typedef", 0).named("Alias")
    target = {
        "missing": None,
        "cycle": alias,
        "primitive": TypeDie("DW_TAG_base_type", 1).named("int"),
        "pointer": TypeDie("DW_TAG_pointer_type", 1),
    }[failure]
    alias.link(target)
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    with pytest.raises(AggregateEvidenceError):
        parser.parse_class_info(alias.cu, alias)


def test_nonaggregate_tag_is_rejected_before_class_cache_lookup() -> None:
    die = TypeDie("DW_TAG_subroutine_type", 3)
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    with pytest.raises(AggregateEvidenceError, match="unsupported aggregate tag"):
        parser.parse_class_info(die.cu, die)

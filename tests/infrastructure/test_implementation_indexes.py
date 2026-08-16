"""Regression tests for reusable method-local relocation and NID indexes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    NidBinding,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_nids import NidIndex
from ddon_dwarf_reconstructor.infrastructure.implementation_relocations import RelocationIndex

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _relocation(identifier: str, offset: int) -> SimpleNamespace:
    return SimpleNamespace(relocation_id=identifier, relocation_offset=offset)


def _nid(identifier: str, name: str) -> NidBinding:
    return NidBinding(
        relocation_id=identifier,
        encoded_symbol=name,
        encoded_nid=name,
        module_id=None,
        library_id=None,
        version_major=None,
        version_minor=None,
        resolved_name=None,
        source=None,
        status=ValidationStatus.NOT_OBSERVED,
    )


def test_relocation_index_selects_half_open_ranges_without_scanning_all_entries() -> None:
    index = RelocationIndex.build(
        (_relocation("late", 0x30), _relocation("first", 0x10), _relocation("middle", 0x20))
    )

    assert index.offsets == (0x10, 0x20, 0x30)
    assert tuple(item.relocation_id for item in index.select(0x10, 0x30)) == (
        "first",
        "middle",
    )
    assert index.select(None, 0x30) == ()


def test_nid_index_preserves_binding_order_for_selected_relocations() -> None:
    index = NidIndex.build((_nid("late", "L"), _nid("first", "F"), _nid("middle", "M")))

    selected = index.select((_relocation("middle", 0x20), _relocation("first", 0x10)))

    assert tuple(item.encoded_symbol for item in selected) == ("F", "M")

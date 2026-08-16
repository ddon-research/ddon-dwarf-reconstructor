"""Tests for DWARF-derived bounded disassembly scope selection."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly_scope import (
    DisassemblyRequest,
    DisassemblyTarget,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import (
    OrbisFunctionSymbol,
    OrbisObjdumpProducer,
)


@pytest.mark.unit
def test_dwarf_target_selection_reaches_dependency_outside_root_prefix() -> None:
    symbols = (
        OrbisFunctionSymbol(0x2000, 0x20, ".text", "MtAllocator::getTotalSize()"),
        OrbisFunctionSymbol(0x3000, 0x20, ".text", "rOther::getTotalSize()"),
    )
    target = DisassemblyTarget(
        target_id="MtAllocator:getTotalSize:1:2",
        declaration_die_offset=1,
        implementation_die_offset=2,
        declaration_cu_offset=3,
        implementation_cu_offset=4,
        ranges=((0x2000, 0x2020),),
        qualified_name="MtAllocator::getTotalSize",
        linkage_name="MtAllocator::getTotalSize()",
        signature="std::size_t getTotalSize()",
    )

    selected = OrbisObjdumpProducer.select_target_symbols(symbols, (target,))

    assert [symbol.name for symbol in selected] == ["MtAllocator::getTotalSize()"]


@pytest.mark.unit
def test_disassembly_request_hash_is_bound_to_target_closure() -> None:
    base = DisassemblyRequest(
        root_symbol="rLayout",
        source_identity="source",
        targets=(
            DisassemblyTarget(
                target_id="a",
                declaration_die_offset=1,
                implementation_die_offset=2,
                declaration_cu_offset=3,
                implementation_cu_offset=4,
                ranges=((0x1000, 0x1010),),
                qualified_name="rLayout::load",
                linkage_name="rLayout::load()",
                signature="void load()",
            ),
        ),
    )
    expanded = DisassemblyRequest(
        root_symbol=base.root_symbol,
        source_identity=base.source_identity,
        targets=base.targets
        + (
            DisassemblyTarget(
                target_id="dependency",
                declaration_die_offset=5,
                implementation_die_offset=6,
                declaration_cu_offset=7,
                implementation_cu_offset=8,
                ranges=((0x2000, 0x2010),),
                qualified_name="MtAllocator::getTotalSize",
                linkage_name="MtAllocator::getTotalSize()",
                signature="std::size_t getTotalSize()",
            ),
        ),
    )

    assert base.scope_hash != expanded.scope_hash

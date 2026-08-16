"""Focused T086 instruction-effect and CFI evidence coverage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction, OrbisReference
from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure import implementation_effects

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_effect_analyzer_normalizes_aliases_widths_and_return_cleanup() -> None:
    result = implementation_effects.analyze_instruction_effects(
        (
            OrbisInstruction(0, "4154", "pushq", "%r12d"),
            OrbisInstruction(2, "415c", "popq", "%r12"),
            OrbisInstruction(4, "c21000", "retq", "$16"),
        )
    )

    assert result.status is ValidationStatus.OBSERVED
    assert result.stack_delta_min == -8
    assert result.stack_delta_max == 24
    assert result.stack_balanced is True
    assert result.callee_saved_preserved is True
    assert "r12" in result.writes


def test_effect_analyzer_joins_equal_conditional_stack_paths() -> None:
    branch = OrbisReference(kind="direct_branch", address=4, resolution_status="resolved")
    jump = OrbisReference(kind="direct_branch", address=5, resolution_status="resolved")
    result = implementation_effects.analyze_instruction_effects(
        (
            OrbisInstruction(0, "53", "push", "%rbx"),
            OrbisInstruction(1, "7402", "je", "0x4", references=(branch,)),
            OrbisInstruction(2, "5b", "pop", "%rbx"),
            OrbisInstruction(3, "eb01", "jmp", "0x5", references=(jump,)),
            OrbisInstruction(4, "5b", "pop", "%rbx"),
            OrbisInstruction(5, "c3", "ret", ""),
        )
    )

    assert result.status is ValidationStatus.OBSERVED
    assert result.stack_balanced is True
    assert result.stack_delta_max == 8
    assert not any("conditional control-flow" in item for item in result.diagnostics)


def test_cfi_inspection_reports_empty_unavailable_and_observed_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert (
        implementation_effects.inspect_cfi(tmp_path / "missing.elf", 0, 0).status
        is ValidationStatus.NOT_OBSERVED
    )
    missing = implementation_effects.inspect_cfi(tmp_path / "missing.elf", 0, 8)
    assert missing.status is ValidationStatus.UNAVAILABLE

    class Entry:
        header = {"initial_location": 0x100, "address_range": 0x20}

    class Dwarf:
        def CFI_entries(self) -> tuple[Entry, ...]:  # noqa: N802
            return (Entry(),)

        def EH_CFI_entries(self) -> tuple[Entry, ...]:  # noqa: N802
            return ()

    class FakeElf:
        def get_dwarf_info(self) -> Dwarf:
            return Dwarf()

    source = tmp_path / "cfi.elf"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(implementation_effects, "ELFFile", lambda _stream: FakeElf())
    observed = implementation_effects.inspect_cfi(source, 0x110, 4)
    assert observed.status is ValidationStatus.OBSERVED

    class GapDwarf:
        def CFI_entries(self) -> tuple[object, ...]:  # noqa: N802
            return (SimpleNamespace(header={"initial_location": 0x100, "address_range": 4}),)

        def EH_CFI_entries(self) -> tuple[object, ...]:  # noqa: N802
            return ()

    monkeypatch.setattr(
        implementation_effects,
        "ELFFile",
        lambda _stream: SimpleNamespace(get_dwarf_info=lambda: GapDwarf()),
    )
    partial = implementation_effects.inspect_cfi(source, 0x100, 8)
    assert partial.status is ValidationStatus.PARTIAL
    assert partial.details["uncovered_ranges"] == ((0x104, 0x108),)

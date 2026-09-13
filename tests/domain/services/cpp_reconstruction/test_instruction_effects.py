"""Pure C++ instruction and bounded control-flow characterization."""

import pytest

from ddon_dwarf_reconstructor.domain.models.cpp_reconstruction.control_flow import ControlFlowStep
from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction, OrbisReference
from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.domain.services.cpp_reconstruction import (
    instruction_effects as implementation_effects,
)
from ddon_dwarf_reconstructor.domain.services.cpp_reconstruction.control_flow import (
    join_conditional_paths,
)

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


def test_effect_analyzer_handles_prefixed_aliases_and_rlayout_load_vector_effects() -> None:
    result = implementation_effects.analyze_instruction_effects(
        (
            OrbisInstruction(0, "4898", "data32 rep movslq", "%eax,%rax"),
            OrbisInstruction(2, "c5fc57c0", "vxorps", "%ymm0,%ymm0,%ymm0"),
            OrbisInstruction(6, "c5fc29442420", "vmovaps", "%ymm0,0x20(%rsp)"),
            OrbisInstruction(12, "c5fc284c2420", "vmovaps", "0x20(%rsp),%ymm1"),
            OrbisInstruction(18, "f081462001", "lock add", "$1,0x20(%rsi)"),
            OrbisInstruction(23, "c3", "retq", ""),
        )
    )

    assert result.status is ValidationStatus.OBSERVED
    assert result.memory_read is True
    assert result.memory_write is True
    assert {"rax", "ymm0", "ymm1"} <= set(result.writes)


def test_effect_analyzer_tracks_stack_alignment_and_frame_state() -> None:
    result = implementation_effects.analyze_instruction_effects(
        (
            OrbisInstruction(0, "55", "push", "%rbp"),
            OrbisInstruction(1, "4889e5", "mov", "%rsp,%rbp"),
            OrbisInstruction(4, "4881e4e0ffffff", "and", "$0xffffffffffffffe0,%rsp"),
            OrbisInstruction(11, "4881ec20100000", "sub", "$0x1020,%rsp"),
            OrbisInstruction(18, "c9", "leave", ""),
            OrbisInstruction(19, "c3", "ret", ""),
        )
    )

    assert result.status is ValidationStatus.OBSERVED
    assert result.stack_balanced is True
    assert result.callee_saved_preserved is True
    assert result.stack_delta_min == -0x1040


def test_conditional_path_budget_and_nonreturning_calls_fail_closed() -> None:
    looping = (
        ControlFlowStep(0, branch_kind="conditional", target=0),
        ControlFlowStep(1, terminal=True),
    )
    limited = join_conditional_paths(looping, 8, max_states=1)
    assert limited.status is ValidationStatus.PARTIAL
    assert "state limit" in limited.diagnostics[0]

    nonreturning = (
        ControlFlowStep(0, branch_kind="conditional", target=2),
        ControlFlowStep(1, terminal=True),
        ControlFlowStep(2, terminal=True, returns=False),
    )
    joined = join_conditional_paths(nonreturning, 0)
    assert joined.status is ValidationStatus.OBSERVED


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

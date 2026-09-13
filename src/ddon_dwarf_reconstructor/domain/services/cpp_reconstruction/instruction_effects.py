"""Conservative instruction-effect evidence for implementation validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ...models.cpp_reconstruction.control_flow import ControlFlowJoin
from ...models.disassembly import OrbisInstruction
from ...models.implementation_validation import (
    InstructionEffects,
    ValidationStatus,
)
from .control_flow import join_conditional_paths, make_control_flow_steps
from .instruction_operands import (
    _CALLEE_SAVED,
    _CONDITIONAL_BRANCHES,
    _FLAG_WRITERS,
    _KNOWN_MNEMONICS,
    _REGISTER_PATTERN,
    _REGISTER_WRITERS,
)
from .instruction_operands import (
    base_mnemonic as _base_mnemonic,
)
from .instruction_operands import (
    canonical_register as _canonical_register,
)
from .instruction_operands import (
    destination_is as _destination_is,
)
from .instruction_operands import (
    destination_register as _destination_register,
)
from .instruction_operands import (
    first_register as _first_register,
)
from .instruction_operands import (
    frame_pointer_displacement as _frame_pointer_displacement,
)
from .instruction_operands import (
    has_memory_operand as _has_memory_operand,
)
from .instruction_operands import (
    is_indirect_target as _is_indirect_target,
)
from .instruction_operands import (
    last_register as _last_register,
)
from .instruction_operands import (
    mentions_stack_pointer as _mentions_stack_pointer,
)
from .instruction_operands import (
    stack_immediate as _stack_immediate,
)
from .instruction_operands import (
    writes_memory as _writes_memory,
)


@dataclass
class _EffectState:
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)
    flags_read: set[str] = field(default_factory=set)
    flags_written: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    saved: set[str] = field(default_factory=set)
    restored: set[str] = field(default_factory=set)
    memory_read: bool = False
    memory_write: bool = False
    indirect_call: bool = False
    stack_delta: int = 0
    stack_min: int = 0
    stack_max: int = 0
    frame_pointer_delta: int | None = None
    uncertain: bool = False
    conditional_branch: bool = False


def analyze_instruction_effects(
    instructions: Iterable[OrbisInstruction],
) -> InstructionEffects:
    """Summarize one linear instruction listing with fail-closed uncertainty."""
    items = tuple(instructions)
    if not items:
        return InstructionEffects(
            status=ValidationStatus.NOT_OBSERVED,
            diagnostics=("no decoded instructions were supplied",),
        )
    state = _EffectState()
    for instruction in items:
        _consume_instruction(state, instruction)
    return _finish_effects(state, items)


def _consume_instruction(state: _EffectState, instruction: OrbisInstruction) -> None:
    mnemonic = _base_mnemonic(instruction.mnemonic)
    operands = instruction.operands.strip()
    registers = tuple(_canonical_register(item) for item in _REGISTER_PATTERN.findall(operands))
    memory = _has_memory_operand(operands)
    if mnemonic not in _KNOWN_MNEMONICS:
        state.uncertain = True
        state.diagnostics.append(f"unknown instruction mnemonic: {instruction.mnemonic}")
    state.reads.update(registers)
    state.memory_read = state.memory_read or memory
    _consume_control(state, mnemonic, operands, instruction)
    _consume_flags_and_memory(state, mnemonic, operands, memory)
    _consume_register_write(state, mnemonic, operands)


def _consume_control(
    state: _EffectState, mnemonic: str, operands: str, instruction: OrbisInstruction
) -> None:
    if mnemonic in {"call", "ret", "push", "pop"}:
        _consume_terminal_control(state, mnemonic, operands, instruction)
        return
    if mnemonic in {"sub", "add", "and"} and _mentions_stack_pointer(operands):
        _consume_stack_control(state, mnemonic, operands)
        return
    if mnemonic in {"mov", "lea", "leave"}:
        _consume_frame_control(state, mnemonic, operands)


def _consume_terminal_control(
    state: _EffectState, mnemonic: str, operands: str, instruction: OrbisInstruction
) -> None:
    if mnemonic == "call":
        _consume_call(state, operands, instruction)
    elif mnemonic == "ret":
        _consume_return(state, operands)
    elif mnemonic == "push":
        _consume_push(state, operands)
    else:
        _consume_pop(state, operands)


def _consume_stack_control(state: _EffectState, mnemonic: str, operands: str) -> None:
    if mnemonic == "and":
        _apply_stack_alignment_mask(state, operands)
        return
    amount = _stack_immediate(operands)
    _update_stack(state, -amount if mnemonic == "sub" else amount)


def _consume_frame_control(state: _EffectState, mnemonic: str, operands: str) -> None:
    if mnemonic == "mov":
        _consume_frame_pointer_move(state, operands)
    elif mnemonic == "lea":
        _consume_frame_pointer_lea(state, operands)
    elif state.frame_pointer_delta is None:
        state.uncertain = True
        state.diagnostics.append("leave changes stack state through unknown frame-pointer state")
    else:
        state.restored.add("rbp")
        _set_stack_delta(state, state.frame_pointer_delta)
        _update_stack(state, 8)
        state.frame_pointer_delta = None


def _consume_call(state: _EffectState, operands: str, instruction: OrbisInstruction) -> None:
    target = instruction.call_target_name
    if target is None and instruction.call_target_address is not None:
        target = f"0x{instruction.call_target_address:x}"
    state.calls.append(target or operands or "indirect")
    state.indirect_call = state.indirect_call or _is_indirect_target(operands, instruction)


def _consume_return(state: _EffectState, operands: str) -> None:
    _update_stack(state, 8 + _stack_immediate(operands))


def _consume_push(state: _EffectState, operands: str) -> None:
    _update_stack(state, -8)
    _track_saved_register(state, operands, state.saved)


def _consume_pop(state: _EffectState, operands: str) -> None:
    _update_stack(state, 8)
    _track_saved_register(state, operands, state.restored)


def _track_saved_register(state: _EffectState, operands: str, target: set[str]) -> None:
    del state
    register = _last_register(operands)
    if register is not None and register in _CALLEE_SAVED:
        target.add(register)


def _consume_flags_and_memory(
    state: _EffectState, mnemonic: str, operands: str, memory: bool
) -> None:
    if mnemonic in _CONDITIONAL_BRANCHES:
        state.conditional_branch = True
        state.flags_read.update({"cf", "of", "sf", "zf", "pf"})
    if mnemonic in _FLAG_WRITERS or mnemonic.startswith("set"):
        state.flags_written.update({"cf", "of", "sf", "zf", "pf", "af"})
    if mnemonic in {"adc", "sbb"}:
        state.flags_read.add("cf")
    if memory and _writes_memory(mnemonic, operands):
        state.memory_write = True


def _consume_register_write(state: _EffectState, mnemonic: str, operands: str) -> None:
    if mnemonic not in _REGISTER_WRITERS:
        return
    destination = _destination_register(operands)
    if destination is not None:
        state.writes.add(destination)


def _update_stack(state: _EffectState, delta: int) -> None:
    state.stack_delta += delta
    state.stack_min = min(state.stack_min, state.stack_delta)
    state.stack_max = max(state.stack_max, state.stack_delta)


def _set_stack_delta(state: _EffectState, value: int) -> None:
    state.stack_delta = value
    state.stack_min = min(state.stack_min, value)
    state.stack_max = max(state.stack_max, value)


def _apply_stack_alignment_mask(state: _EffectState, operands: str) -> None:
    mask = _stack_immediate(operands)
    if mask >= 0 or not _destination_is(operands, "rsp"):
        state.uncertain = True
        state.diagnostics.append("stack alignment mask is not a proven negative rsp mask")
        return
    _set_stack_delta(state, state.stack_delta & mask)


def _consume_frame_pointer_move(state: _EffectState, operands: str) -> None:
    source = _first_register(operands)
    destination = _destination_register(operands)
    if source == "rsp" and destination == "rbp":
        state.frame_pointer_delta = state.stack_delta
    elif source == "rbp" and destination == "rsp" and state.frame_pointer_delta is not None:
        _set_stack_delta(state, state.frame_pointer_delta)


def _consume_frame_pointer_lea(state: _EffectState, operands: str) -> None:
    if _destination_register(operands) != "rsp" or state.frame_pointer_delta is None:
        return
    displacement = _frame_pointer_displacement(operands)
    if displacement is not None:
        _set_stack_delta(state, state.frame_pointer_delta + displacement)


def _finish_effects(state: _EffectState, items: tuple[OrbisInstruction, ...]) -> InstructionEffects:
    preserved = _callee_saved_preserved(state)
    if not preserved:
        state.diagnostics.append("callee-saved register write lacks a matched save/restore")
    expected_delta, conflicting = _return_cleanup(items)
    if conflicting:
        state.uncertain = True
        state.diagnostics.append("conflicting return-immediate cleanup paths")
    expected_delta, joined, preserved, balanced = _resolve_effect_paths(
        state, items, expected_delta, preserved
    )
    if state.uncertain:
        state.diagnostics.append("instruction effects are incomplete for this listing")
    status = _effect_status(state, expected_delta, preserved)
    return InstructionEffects(
        status=status,
        reads=tuple(sorted(state.reads)),
        writes=tuple(sorted(state.writes)),
        flags_read=tuple(sorted(state.flags_read)),
        flags_written=tuple(sorted(state.flags_written)),
        memory_read=state.memory_read,
        memory_write=state.memory_write,
        calls=tuple(state.calls),
        indirect_call=state.indirect_call,
        stack_delta_min=state.stack_min,
        stack_delta_max=state.stack_max,
        stack_balanced=balanced,
        callee_saved_preserved=preserved,
        diagnostics=tuple(dict.fromkeys(state.diagnostics)),
    )


def _return_cleanup(items: tuple[OrbisInstruction, ...]) -> tuple[int, bool]:
    deltas = _return_stack_deltas(items)
    if not deltas:
        return 0, False
    if len(set(deltas)) == 1:
        return deltas[0], False
    return 0, True


def _resolve_effect_paths(
    state: _EffectState,
    items: tuple[OrbisInstruction, ...],
    expected_delta: int,
    preserved: bool,
) -> tuple[int, bool, bool, bool]:
    join = _conditional_join(items, expected_delta, state.conditional_branch)
    joined = join is not None and join.status is ValidationStatus.OBSERVED
    if joined:
        assert join is not None
        preserved = _apply_joined_effects(state, join, expected_delta)
    else:
        _append_unjoined_diagnostics(state, join, expected_delta)
    balanced = joined or _stack_balanced(state, expected_delta)
    return expected_delta, joined, preserved, balanced


def _apply_joined_effects(state: _EffectState, join: ControlFlowJoin, expected_delta: int) -> bool:
    state.stack_delta = _value_or(join.stack_delta, expected_delta)
    state.stack_min = _value_or(join.stack_min, state.stack_min)
    state.stack_max = _value_or(join.stack_max, state.stack_max)
    return join.callee_saved_preserved is True


def _value_or(value: int | None, fallback: int) -> int:
    return fallback if value is None else value


def _append_unjoined_diagnostics(
    state: _EffectState, join: ControlFlowJoin | None, expected_delta: int
) -> None:
    if join is not None:
        state.diagnostics.extend(join.diagnostics)
    if state.stack_delta not in {0, expected_delta}:
        state.diagnostics.append(f"linear stack delta is {state.stack_delta} bytes")
    if state.conditional_branch:
        state.diagnostics.append("conditional control-flow paths were not symbolically joined")


def _conditional_join(
    items: tuple[OrbisInstruction, ...], expected_delta: int, has_conditional: bool
) -> ControlFlowJoin | None:
    if not has_conditional:
        return None
    stack_deltas = _path_stack_deltas(items)
    steps = make_control_flow_steps(
        items,
        normalize=_base_mnemonic,
        target=_branch_target,
        stack_delta=lambda item: stack_deltas.get(item.address, _instruction_stack_delta(item)),
        saved=_callee_saved_set,
        destination=_callee_saved_destination,
        conditional=_CONDITIONAL_BRANCHES,
        known=_KNOWN_MNEMONICS,
    )
    return join_conditional_paths(
        steps,
        expected_delta,
        max_states=min(16384, max(2048, len(items) * 16)),
    )


def _path_stack_deltas(items: tuple[OrbisInstruction, ...]) -> dict[int, int]:
    """Calculate stack transitions with the same frame model as linear effects."""
    state = _EffectState()
    result: dict[int, int] = {}
    for item in items:
        before = state.stack_delta
        _consume_control(state, _base_mnemonic(item.mnemonic), item.operands, item)
        result[item.address] = state.stack_delta - before
    return result


def _callee_saved_destination(operands: str) -> str | None:
    destination = _destination_register(operands)
    return destination if destination in _CALLEE_SAVED else None


def _branch_target(instruction: OrbisInstruction) -> int | None:
    for reference in instruction.references:
        if reference.kind == "direct_branch" and reference.address is not None:
            return reference.address
    parts = instruction.operands.strip().split(maxsplit=1)
    if not parts:
        return None
    candidate = parts[0].rstrip(",")
    if not re.fullmatch(r"(?:0x)?[0-9a-f]+", candidate, re.IGNORECASE):
        return None
    try:
        return int(candidate, 0 if candidate.lower().startswith("0x") else 16)
    except ValueError:
        return None


def _instruction_stack_delta(instruction: OrbisInstruction) -> int:
    mnemonic = _base_mnemonic(instruction.mnemonic)
    if mnemonic == "push":
        return -8
    if mnemonic == "pop":
        return 8
    if mnemonic == "ret":
        return 8 + _stack_immediate(instruction.operands)
    if mnemonic in {"sub", "add"} and _mentions_stack_pointer(instruction.operands):
        amount = _stack_immediate(instruction.operands)
        return -amount if mnemonic == "sub" else amount
    if mnemonic == "and" and _mentions_stack_pointer(instruction.operands):
        # The exact mask transition is state-dependent; the linear analyzer
        # proves it while the generic path join remains conservative.
        return 0
    return 0


def _callee_saved_set(instruction: OrbisInstruction, mnemonic: str) -> frozenset[str]:
    if _base_mnemonic(instruction.mnemonic) != mnemonic:
        return frozenset()
    register = _last_register(instruction.operands)
    if register is None or register not in _CALLEE_SAVED:
        return frozenset()
    return frozenset({register})


def _callee_saved_preserved(state: _EffectState) -> bool:
    callee_writes = state.writes & _CALLEE_SAVED
    return not callee_writes or (callee_writes <= state.saved and callee_writes <= state.restored)


def _return_stack_deltas(items: tuple[OrbisInstruction, ...]) -> tuple[int, ...]:
    return tuple(
        8 + _stack_immediate(item.operands)
        for item in items
        if _base_mnemonic(item.mnemonic) == "ret"
    )


def _stack_balanced(state: _EffectState, expected_delta: int) -> bool:
    return (
        state.stack_delta == expected_delta and not state.conditional_branch and not state.uncertain
    )


def _effect_status(state: _EffectState, expected_delta: int, preserved: bool) -> ValidationStatus:
    status = ValidationStatus.OBSERVED if not state.diagnostics else ValidationStatus.PARTIAL
    if state.stack_delta not in {0, expected_delta} or not preserved:
        return ValidationStatus.FAILED
    return status


__all__ = ["analyze_instruction_effects"]

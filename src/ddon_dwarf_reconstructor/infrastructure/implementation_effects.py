"""Conservative instruction-effect and CFI evidence for implementation validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.disassembly import OrbisInstruction
from ..domain.models.implementation_validation import (
    EvidenceStatus,
    InstructionEffects,
    ValidationStatus,
)
from .implementation_parity import ControlFlowJoin, join_conditional_paths, make_control_flow_steps

_REGISTER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])%?(?:r(?:[89]|1[0-5])(?:[bwd])?|"
    r"r(?:[abcd]x|[sb]p|[sd]i|ip)|"
    r"e?[abcd]x|e?[sb]p|e?[sd]i|[abcd][lh]|sil|dil|spl|bpl|"
    r"xmm\d+|ymm\d+|zmm\d+)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_IMMEDIATE_PATTERN = re.compile(r"(?:\$|#)?(?:-?0x[0-9a-f]+|-?\d+)$", re.IGNORECASE)
_CALLEE_SAVED = frozenset({"rbx", "rbp", "r12", "r13", "r14", "r15"})
_CONDITIONAL_BRANCHES = frozenset(  # noqa: SIM905
    "ja jae jb jbe jc je jg jge jl jle jna jnae jnb jnbe jnc jne jng jnge "  # noqa: SIM905
    "jnl jnle jno jnp jns jnz jo jp jpe jpo js jz jecxz jrcxz jcxz loop "
    "loope loopne loopnz loopz".split()  # noqa: SIM905
)
_FLAG_WRITERS = frozenset({"add", "and", "cmp", "dec", "inc", "or", "sbb", "sub", "test", "xor"})
_KNOWN_MNEMONICS = (
    frozenset(  # noqa: SIM905
        "adc add and call clc cld cmc cmp cqo cqto dec div idiv imul inc jmp lea "  # noqa: SIM905
        "leave mov movabs movdqa movdqu movaps movups mul neg nop not or pop "
        "push ret sal rol ror sar sbb seta setae setb setbe sete setg setge "
        "setl setle setne setno seto sets shl shr sub syscall test vzeroupper xor".split()  # noqa: SIM905
    )
    | _CONDITIONAL_BRANCHES
)
_REGISTER_WRITERS = frozenset(  # noqa: SIM905
    "add and cmp dec idiv imul inc lea mov movabs neg not or pop rol ror sar "  # noqa: SIM905
    "seta setae setb setbe sete setg setge setl setle setne setno seto sets "
    "shl shr sub xor".split()  # noqa: SIM905
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
    if mnemonic == "call":
        _consume_call(state, operands, instruction)
    elif mnemonic == "ret":
        _consume_return(state, operands)
    elif mnemonic == "push":
        _consume_push(state, operands)
    elif mnemonic == "pop":
        _consume_pop(state, operands)
    elif mnemonic in {"sub", "add"} and _mentions_stack_pointer(operands):
        amount = _stack_immediate(operands)
        _update_stack(state, -amount if mnemonic == "sub" else amount)
    elif mnemonic == "leave":
        state.uncertain = True
        state.diagnostics.append("leave changes stack state through frame-pointer state")


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
    steps = make_control_flow_steps(
        items,
        normalize=_base_mnemonic,
        target=_branch_target,
        stack_delta=_instruction_stack_delta,
        saved=_callee_saved_set,
        destination=_callee_saved_destination,
        conditional=_CONDITIONAL_BRANCHES,
        known=_KNOWN_MNEMONICS,
    )
    return join_conditional_paths(steps, expected_delta)


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
    return not callee_writes or callee_writes <= state.saved and callee_writes <= state.restored


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


def inspect_cfi(source: Path, start: int, size: int) -> EvidenceStatus:
    """Locate CFI covering a method range without treating absence as success."""
    if size <= 0:
        return EvidenceStatus(ValidationStatus.NOT_OBSERVED, ("method range is empty",))
    entries, error = _read_cfi_entries(source)
    if error is not None:
        return error
    end = start + size
    spans = sorted(span for entry in entries if (span := _cfi_span(entry, start, end)) is not None)
    if not spans:
        return EvidenceStatus(
            ValidationStatus.NOT_OBSERVED,
            ("no .debug_frame or .eh_frame entry covers the method range",),
        )
    gaps = _cfi_gaps(spans, start, end)
    if gaps:
        return EvidenceStatus(
            ValidationStatus.PARTIAL,
            ("CFI entries overlap the method but do not join across its full range",),
            {"covering_entries": len(spans), "uncovered_ranges": gaps},
        )
    return EvidenceStatus(
        ValidationStatus.OBSERVED,
        details={"covering_entries": len(spans), "covered_range": (start, end)},
    )


def _read_cfi_entries(source: Path) -> tuple[tuple[object, ...], EvidenceStatus | None]:
    entries: list[object] = []
    try:
        with source.open("rb") as stream:
            dwarf = ELFFile(stream).get_dwarf_info()
            for getter_name in ("CFI_entries", "EH_CFI_entries"):
                getter = getattr(dwarf, getter_name, None)
                if getter is None:
                    continue
                try:
                    entries.extend(getter())
                except Exception as error:  # parser-specific diagnostics are evidence
                    return (), EvidenceStatus(
                        ValidationStatus.PARTIAL,
                        (f"{getter_name} parsing failed: {type(error).__name__}",),
                    )
    except (ELFError, OSError, ValueError) as error:
        return (), EvidenceStatus(
            ValidationStatus.UNAVAILABLE,
            (f"CFI source could not be opened: {type(error).__name__}",),
        )
    return tuple(entries), None


def _cfi_span(entry: object, start: int, end: int) -> tuple[int, int] | None:
    header = getattr(entry, "header", {})
    initial = _header_int(header, "initial_location")
    span = _header_int(header, "address_range")
    if initial is None or span is None or span <= 0:
        return None
    left = max(initial, start)
    right = min(initial + span, end)
    return (left, right) if left < right else None


def _cfi_gaps(spans: list[tuple[int, int]], start: int, end: int) -> tuple[tuple[int, int], ...]:
    cursor = start
    gaps: list[tuple[int, int]] = []
    for left, right in spans:
        if left > cursor:
            gaps.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append((cursor, end))
    return tuple(gaps)


def _base_mnemonic(value: str) -> str:
    mnemonic = value.strip().lower().split(".", 1)[0] if value else ""
    for prefix in ("repnz", "repne", "repe", "repz", "rep", "lock"):
        if mnemonic.startswith(prefix) and len(mnemonic) > len(prefix):
            mnemonic = mnemonic[len(prefix) :]
            break
    mnemonic = {"sal": "shl", "retn": "ret", "retq": "ret"}.get(mnemonic, mnemonic)
    if mnemonic.endswith(("q", "w", "l", "b")) and mnemonic[:-1] in _KNOWN_MNEMONICS:
        return mnemonic[:-1]
    return mnemonic


def _canonical_register(value: str) -> str:
    register = value.lower().lstrip("%")
    if re.fullmatch(r"r(?:[89]|1[0-5])[bwd]", register):
        register = register[:-1]
    aliases = {
        "eax": "rax",
        "ax": "rax",
        "al": "rax",
        "ah": "rax",
        "ebx": "rbx",
        "bx": "rbx",
        "bl": "rbx",
        "bh": "rbx",
        "ecx": "rcx",
        "cx": "rcx",
        "cl": "rcx",
        "ch": "rcx",
        "edx": "rdx",
        "dx": "rdx",
        "dl": "rdx",
        "dh": "rdx",
        "esp": "rsp",
        "sp": "rsp",
        "spl": "rsp",
        "ebp": "rbp",
        "bp": "rbp",
        "bpl": "rbp",
        "esi": "rsi",
        "si": "rsi",
        "sil": "rsi",
        "edi": "rdi",
        "di": "rdi",
        "dil": "rdi",
    }
    return aliases.get(register, register)


def _has_memory_operand(operands: str) -> bool:
    return bool(re.search(r"\([^)]*\)|\[[^]]+\]", operands))


def _writes_memory(mnemonic: str, operands: str) -> bool:
    if not _has_memory_operand(operands):
        return False
    if mnemonic in {"cmp", "test", "lea"}:
        return False
    if mnemonic in {"push", "call"}:
        return True
    parts = [part.strip() for part in operands.split(",") if part.strip()]
    return bool(parts) and _has_memory_operand(parts[-1])


def _destination_register(operands: str) -> str | None:
    parts = [part.strip() for part in operands.split(",") if part.strip()]
    if not parts:
        return None
    match = _REGISTER_PATTERN.search(parts[-1])
    return _canonical_register(match.group(0)) if match else None


def _last_register(operands: str) -> str | None:
    matches = _REGISTER_PATTERN.findall(operands)
    return _canonical_register(matches[-1]) if matches else None


def _mentions_stack_pointer(operands: str) -> bool:
    return any(_canonical_register(item) == "rsp" for item in _REGISTER_PATTERN.findall(operands))


def _stack_immediate(operands: str) -> int:
    for part in (item.strip() for item in operands.split(",")):
        candidate = part.removeprefix("$").removeprefix("#")
        if _IMMEDIATE_PATTERN.fullmatch(part) or _IMMEDIATE_PATTERN.fullmatch(candidate):
            try:
                return int(candidate, 0)
            except ValueError:
                return 0
    return 0


def _is_indirect_target(operands: str, instruction: OrbisInstruction) -> bool:
    if instruction.call_target_address is not None or instruction.call_target_name is not None:
        return False
    value = operands.strip().lstrip("*")
    return not bool(_IMMEDIATE_PATTERN.fullmatch(value))


def _header_int(header: object, key: str) -> int | None:
    try:
        value = header[key]  # type: ignore[index]
    except KeyError, TypeError:
        return None
    return int(value) if value is not None else None


__all__ = ["analyze_instruction_effects", "inspect_cfi"]

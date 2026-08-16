"""Independent static parity checks for assembled target objects."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..domain.models.disassembly import OrbisInstruction, OrbisReference
from ..domain.models.implementation_validation import ValidationStatus

_PathState = tuple[
    int,
    int,
    int,
    int,
    frozenset[str],
    frozenset[str],
    frozenset[str],
    bool,
    int,
]
_PathTerminal = tuple[int, int, int, frozenset[str], frozenset[str], frozenset[str], bool]


@dataclass(frozen=True, slots=True)
class ControlFlowStep:
    """Bounded effect summary for one instruction in a method CFG."""

    address: int
    branch_kind: str = "normal"
    target: int | None = None
    stack_delta: int = 0
    terminal: bool = False
    uncertain: bool = False
    saved: frozenset[str] = frozenset()
    restored: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ControlFlowJoin:
    """Result of joining bounded conditional paths without guessing missing edges."""

    status: ValidationStatus
    stack_delta: int | None = None
    stack_min: int | None = None
    stack_max: int | None = None
    callee_saved_preserved: bool | None = None
    diagnostics: tuple[str, ...] = ()


def make_control_flow_steps(
    items: tuple[OrbisInstruction, ...],
    *,
    normalize: Callable[[str], str],
    target: Callable[[OrbisInstruction], int | None],
    stack_delta: Callable[[OrbisInstruction], int],
    saved: Callable[[OrbisInstruction, str], frozenset[str]],
    destination: Callable[[str], str | None],
    conditional: frozenset[str],
    known: frozenset[str],
) -> tuple[ControlFlowStep, ...]:
    """Build CFG steps while leaving instruction policy with the effect analyzer."""
    steps: list[ControlFlowStep] = []
    for item in items:
        mnemonic = normalize(item.mnemonic)
        destination_register = destination(item.operands)
        writes = (
            frozenset({destination_register}) if destination_register is not None else frozenset()
        )
        steps.append(
            ControlFlowStep(
                address=item.address,
                branch_kind=(
                    "conditional"
                    if mnemonic in conditional
                    else "unconditional"
                    if mnemonic == "jmp"
                    else "normal"
                ),
                target=target(item),
                stack_delta=stack_delta(item),
                terminal=mnemonic == "ret",
                uncertain=mnemonic not in known or mnemonic == "leave",
                saved=saved(item, "push"),
                restored=saved(item, "pop"),
                writes=writes,
            )
        )
    return tuple(steps)


def join_conditional_paths(
    steps: tuple[ControlFlowStep, ...],
    expected_delta: int,
    *,
    max_states: int = 512,
) -> ControlFlowJoin:
    """Join simple method CFG paths and fail closed on unresolved or conflicting paths."""
    if not any(step.branch_kind == "conditional" for step in steps):
        return ControlFlowJoin(ValidationStatus.NOT_OBSERVED)
    addresses = {step.address: index for index, step in enumerate(steps)}
    terminals, diagnostic = _walk_paths(steps, addresses, max_states)
    if diagnostic is not None:
        return _join_partial(diagnostic)
    return _summarize_paths(terminals, expected_delta)


def _walk_paths(
    steps: tuple[ControlFlowStep, ...], addresses: dict[int, int], max_states: int
) -> tuple[list[_PathTerminal], str | None]:
    queue = deque([(0, 0, 0, 0, frozenset(), frozenset(), frozenset(), False, 0)])
    seen: set[tuple[object, ...]] = set()
    terminals: list[_PathTerminal] = []
    while queue:
        terminals_for_state, successors, diagnostic = _expand_path(
            queue.popleft(), steps, addresses, seen, max_states
        )
        if diagnostic is not None:
            return terminals, diagnostic
        terminals.extend(terminals_for_state)
        queue.extend(successors)
    if not terminals:
        return terminals, "conditional control-flow has no bounded terminal path"
    return terminals, None


def _expand_path(
    state: _PathState,
    steps: tuple[ControlFlowStep, ...],
    addresses: dict[int, int],
    seen: set[tuple[object, ...]],
    max_states: int,
) -> tuple[tuple[_PathTerminal, ...], tuple[_PathState, ...], str | None]:
    index, delta, minimum, maximum, saved, restored, writes, uncertain, depth = state
    if not _path_index_valid(index, len(steps)):
        return (), (), "a control-flow successor leaves the decoded method range"
    if depth > max(2, len(steps) * 2):
        return (), (), "conditional control-flow path did not reach a bounded join"
    step = steps[index]
    delta += step.stack_delta
    minimum = min(minimum, delta)
    maximum = max(maximum, delta)
    saved |= step.saved
    restored |= step.restored
    writes |= step.writes
    uncertain = uncertain or step.uncertain
    signature = (index, delta, saved, restored, writes, uncertain)
    if signature in seen:
        return (), (), None
    seen.add(signature)
    if len(seen) > max_states:
        return (), (), "conditional control-flow path state limit was exceeded"
    if _path_is_terminal(step, index, len(steps)):
        terminal = (delta, minimum, maximum, saved, restored, writes, uncertain)
        return (terminal,), (), None
    successors = _successors(index, step, addresses, len(steps))
    if successors is None:
        return (), (), "conditional control-flow target is unresolved"
    return (
        (),
        tuple(
            (successor, delta, minimum, maximum, saved, restored, writes, uncertain, depth + 1)
            for successor in successors
        ),
        None,
    )


def _path_index_valid(index: int, count: int) -> bool:
    return 0 <= index < count


def _path_is_terminal(step: ControlFlowStep, index: int, count: int) -> bool:
    return step.terminal or index == count - 1


def _summarize_paths(
    terminals: list[_PathTerminal],
    expected_delta: int,
) -> ControlFlowJoin:
    deltas = {item[0] for item in terminals}
    preserved = all(not (item[6] or item[5] - item[3] - item[4]) for item in terminals)
    if len(deltas) != 1 or next(iter(deltas)) != expected_delta:
        return ControlFlowJoin(
            ValidationStatus.FAILED,
            diagnostics=("conditional control-flow paths have conflicting stack cleanup",),
            callee_saved_preserved=preserved,
        )
    if not preserved:
        return ControlFlowJoin(
            ValidationStatus.FAILED,
            diagnostics=("conditional control-flow paths do not preserve callee-saved registers",),
            callee_saved_preserved=False,
        )
    return ControlFlowJoin(
        ValidationStatus.OBSERVED,
        stack_delta=next(iter(deltas)),
        stack_min=min(item[1] for item in terminals),
        stack_max=max(item[2] for item in terminals),
        callee_saved_preserved=True,
    )


def _successors(
    index: int,
    step: ControlFlowStep,
    addresses: dict[int, int],
    count: int,
) -> tuple[int, ...] | None:
    if step.branch_kind in {"conditional", "unconditional"}:
        if step.target is None or step.target not in addresses:
            return None
        target = addresses[step.target]
        if step.branch_kind == "conditional":
            return (target, index + 1) if index + 1 < count else (target,)
        return (target,)
    return (index + 1,) if index + 1 < count else ()


def _join_partial(diagnostic: str) -> ControlFlowJoin:
    return ControlFlowJoin(ValidationStatus.PARTIAL, diagnostics=(diagnostic,))


def compare_static_edges(
    source: Iterable[OrbisInstruction],
    generated: Iterable[OrbisInstruction],
) -> tuple[ValidationStatus, ValidationStatus, tuple[str, ...]]:
    """Compare normalized branch and call edges from two target disassemblies.

    The generated object is assembled at address zero, so absolute addresses are
    normalized to the first instruction in each listing.  The comparison is
    intentionally conservative: a missing decoded instruction or an unresolved
    edge is never treated as an equivalent empty edge.
    """
    source_items = tuple(source)
    generated_items = tuple(generated)
    if not source_items or not generated_items:
        return (
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            ("source and generated disassembly are both required for static edge parity",),
        )
    if len(source_items) != len(generated_items):
        diagnostic = (
            "source and generated target disassemblies decoded different instruction counts: "
            f"{len(source_items)} != {len(generated_items)}"
        )
        return ValidationStatus.FAILED, ValidationStatus.FAILED, (diagnostic,)
    source_base = source_items[0].address
    generated_base = generated_items[0].address
    source_branches = _edge_signatures(source_items, source_base, "branch")
    generated_branches = _edge_signatures(generated_items, generated_base, "branch")
    source_calls = _edge_signatures(source_items, source_base, "call")
    generated_calls = _edge_signatures(generated_items, generated_base, "call")
    diagnostics: list[str] = []
    cfg_status = _edge_status(source_branches, generated_branches, "branch", diagnostics)
    call_status = _edge_status(source_calls, generated_calls, "call", diagnostics)
    return cfg_status, call_status, tuple(diagnostics)


def _edge_signatures(
    instructions: tuple[OrbisInstruction, ...], base: int, family: str
) -> tuple[tuple[object, ...], ...]:
    end = max(item.address + _byte_length(item) for item in instructions)
    signatures: list[tuple[object, ...]] = []
    for instruction in instructions:
        offset = instruction.address - base
        for reference in instruction.references:
            if not _belongs_to_family(reference, family):
                continue
            target = _normalized_target(reference, base, end)
            signatures.append((offset, reference.kind, target))
    return tuple(signatures)


def _belongs_to_family(reference: OrbisReference, family: str) -> bool:
    if family == "branch":
        return reference.kind in {"direct_branch", "indirect_branch"}
    return reference.kind in {"direct_call", "indirect_call"}


def _normalized_target(reference: OrbisReference, base: int, end: int) -> tuple[object, ...]:
    if "indirect" in reference.kind:
        return ("indirect", reference.resolved_name)
    if reference.address is not None:
        relative = reference.address - base
        scope = "internal" if base <= reference.address < end else "external"
        return scope, relative
    if reference.resolved_name is not None:
        return "name", reference.resolved_name
    return "unresolved", reference.resolution_status


def _edge_status(
    source: tuple[tuple[object, ...], ...],
    generated: tuple[tuple[object, ...], ...],
    family: str,
    diagnostics: list[str],
) -> ValidationStatus:
    if source == generated:
        return ValidationStatus.OBSERVED
    diagnostics.append(f"normalized {family} edges differ")
    return ValidationStatus.FAILED


def _byte_length(instruction: OrbisInstruction) -> int:
    value = instruction.raw_bytes.replace(" ", "")
    try:
        return max(1, len(bytes.fromhex(value)))
    except ValueError:
        return 1


__all__ = ["compare_static_edges"]

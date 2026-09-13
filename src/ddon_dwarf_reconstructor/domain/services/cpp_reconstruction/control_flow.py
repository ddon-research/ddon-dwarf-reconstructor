"""Independent static parity checks for assembled target objects."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import replace

from ...models.cpp_reconstruction.control_flow import ControlFlowJoin, ControlFlowStep
from ...models.disassembly import OrbisInstruction, OrbisReference
from ...models.implementation_validation import (
    CompilerEvidence,
    SemanticParity,
    StaticEquivalenceDisposition,
    ValidationStatus,
)

_NON_RETURNING_CALL_MARKERS = (
    "__stack_chk_fail",
    "__cxa_pure_virtual",
    "abort",
    "exit",
    "terminate",
)

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
_PathTerminal = tuple[
    int,
    int,
    int,
    frozenset[str],
    frozenset[str],
    frozenset[str],
    bool,
    bool,
]


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
        non_returning = _is_non_returning_call(item, mnemonic)
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
                terminal=mnemonic == "ret" or non_returning,
                returns=not non_returning,
                uncertain=mnemonic not in known or mnemonic == "leave",
                saved=saved(item, "push"),
                restored=saved(item, "pop"),
                writes=writes,
            )
        )
    return tuple(steps)


def _is_non_returning_call(instruction: OrbisInstruction, mnemonic: str) -> bool:
    if mnemonic != "call":
        return False
    target = (instruction.call_target_name or "").casefold()
    return any(marker in target for marker in _NON_RETURNING_CALL_MARKERS)


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
        terminal = (delta, minimum, maximum, saved, restored, writes, uncertain, step.returns)
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
    returning = _returning_paths(terminals)
    if not returning:
        return ControlFlowJoin(
            ValidationStatus.PARTIAL,
            diagnostics=("conditional control-flow has no returning terminal path",),
        )
    deltas = {item[0] for item in returning}
    preserved = _paths_preserve_callee_saved(returning)
    if not _has_expected_cleanup(deltas, expected_delta):
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
        stack_min=min(item[1] for item in returning),
        stack_max=max(item[2] for item in returning),
        callee_saved_preserved=True,
    )


def _returning_paths(terminals: list[_PathTerminal]) -> list[_PathTerminal]:
    return [item for item in terminals if item[7]]


def _paths_preserve_callee_saved(paths: list[_PathTerminal]) -> bool:
    return all(not (item[6] or item[5] - item[3] - item[4]) for item in paths)


def _has_expected_cleanup(deltas: set[int], expected_delta: int) -> bool:
    return len(deltas) == 1 and next(iter(deltas), None) == expected_delta


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


def normalize_parity(
    parity: SemanticParity,
    compiler_status: ValidationStatus | None = None,
    *,
    required_dimensions: tuple[tuple[str, ValidationStatus], ...] = (),
    compiler_evidence: CompilerEvidence | None = None,
) -> SemanticParity:
    """Join parity dimensions without promoting incomplete target evidence."""
    status = _normalized_parity_status(parity, compiler_status, required_dimensions)
    diagnostics = _normalized_parity_diagnostics(parity, compiler_status, required_dimensions)
    disposition = _static_equivalence_disposition(
        parity,
        compiler_status,
        required_dimensions,
        compiler_evidence,
    )
    return replace(
        parity,
        status=status,
        static_equivalence=disposition,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )


def _static_equivalence_disposition(
    parity: SemanticParity,
    compiler_status: ValidationStatus | None,
    required_dimensions: tuple[tuple[str, ValidationStatus], ...],
    compiler_evidence: CompilerEvidence | None,
) -> StaticEquivalenceDisposition:
    dimension_statuses = (
        parity.byte_status,
        parity.cfg_status,
        parity.external_edge_status,
        parity.effect_status,
        *(value for _label, value in required_dimensions),
    )
    failure = _static_disposition_failure(parity, compiler_status, required_dimensions)
    if failure is not None:
        return failure
    if compiler_status is not ValidationStatus.OBSERVED:
        return StaticEquivalenceDisposition.NOT_PROMOTED
    if any(status is not ValidationStatus.OBSERVED for status in dimension_statuses):
        return StaticEquivalenceDisposition.NOT_PROMOTED
    if not _accepted_target_object(compiler_evidence):
        return StaticEquivalenceDisposition.NOT_PROMOTED
    return StaticEquivalenceDisposition.TARGET_OBJECT_EQUIVALENT


def _static_disposition_failure(
    parity: SemanticParity,
    compiler_status: ValidationStatus | None,
    required_dimensions: tuple[tuple[str, ValidationStatus], ...],
) -> StaticEquivalenceDisposition | None:
    if parity.byte_status is ValidationStatus.FAILED:
        return StaticEquivalenceDisposition.CONFLICTING
    edge_statuses = (parity.cfg_status, parity.external_edge_status)
    if any(status is ValidationStatus.FAILED for status in edge_statuses):
        return StaticEquivalenceDisposition.CONFLICTING
    if parity.effect_status is ValidationStatus.FAILED or any(
        value is ValidationStatus.FAILED for _label, value in required_dimensions
    ):
        return StaticEquivalenceDisposition.FAILED
    if parity.status is ValidationStatus.FAILED or compiler_status is ValidationStatus.FAILED:
        return StaticEquivalenceDisposition.FAILED
    return None


def _accepted_target_object(compiler: CompilerEvidence | None) -> bool:
    if compiler is None or compiler.status is not ValidationStatus.OBSERVED:
        return False
    if not compiler.output_path or not compiler.output_sha256:
        return False
    metadata = compiler.object_metadata
    return (
        isinstance(metadata.get("e_flags"), int)
        and isinstance(metadata.get("section_names"), (tuple, list))
        and bool(metadata.get("section_names"))
    )


def _normalized_parity_status(
    parity: SemanticParity,
    compiler_status: ValidationStatus | None,
    required_dimensions: tuple[tuple[str, ValidationStatus], ...] = (),
) -> ValidationStatus:
    statuses = (
        parity.byte_status,
        parity.cfg_status,
        parity.external_edge_status,
        parity.effect_status,
        *(value for _label, value in required_dimensions),
    )
    if parity.status is ValidationStatus.FAILED or ValidationStatus.FAILED in statuses:
        return ValidationStatus.FAILED
    if all(item is ValidationStatus.OBSERVED for item in statuses) and compiler_status in (
        None,
        ValidationStatus.OBSERVED,
    ):
        return ValidationStatus.OBSERVED
    if parity.status is ValidationStatus.NOT_OBSERVED and all(
        item is ValidationStatus.NOT_OBSERVED for item in statuses
    ):
        return ValidationStatus.NOT_OBSERVED
    return ValidationStatus.PARTIAL


def _normalized_parity_diagnostics(
    parity: SemanticParity,
    compiler_status: ValidationStatus | None,
    required_dimensions: tuple[tuple[str, ValidationStatus], ...] = (),
) -> tuple[str, ...]:
    missing = tuple(
        label
        for label, value in (
            ("CFG", parity.cfg_status),
            ("external edges", parity.external_edge_status),
        )
        if value is not ValidationStatus.OBSERVED
    )
    missing += tuple(
        label for label, value in required_dimensions if value is not ValidationStatus.OBSERVED
    )
    diagnostics = tuple(parity.diagnostics)
    if missing:
        diagnostics += (
            "static parity dimensions not independently observed: " + ", ".join(missing),
        )
    if compiler_status not in (None, ValidationStatus.OBSERVED):
        diagnostics += ("accepted Orbis target-object generation was not observed",)
    return diagnostics


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
            kind = "resolved" if reference.address is not None else reference.kind
            signatures.append((offset, kind, target))
    return tuple(signatures)


def _belongs_to_family(reference: OrbisReference, family: str) -> bool:
    if family == "branch":
        return reference.kind in {"direct_branch", "indirect_branch"}
    return reference.kind in {"direct_call", "indirect_call"}


def _normalized_target(reference: OrbisReference, base: int, end: int) -> tuple[object, ...]:
    if reference.address is not None:
        relative = reference.address - base
        if relative >= 1 << 63:
            relative -= 1 << 64
        scope = "internal" if base <= reference.address < end else "external"
        return scope, relative
    if "indirect" in reference.kind:
        return ("indirect", reference.resolved_name)
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

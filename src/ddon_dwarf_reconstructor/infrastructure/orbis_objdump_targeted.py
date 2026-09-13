"""Target-aware LLVM disassembly slices kept additive to Orbis evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ..domain.models.disassembly import (
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisTargetedDisassemblyCrossCheck,
    OrbisToolInvocation,
)
from .orbis_objdump_parsing import parse_instructions
from .orbis_objdump_profiles import (
    LLVM_TARGET_CAPABILITY_FLAGS,
    LLVM_TARGET_DISASSEMBLY_FLAGS,
    LLVM_TARGET_PROFILE,
)

if TYPE_CHECKING:
    from .orbis_objdump import OrbisObjdumpProducer, _ProductionContext


@dataclass(frozen=True, slots=True)
class _TargetedSliceEvidence:
    """Comparison result for one bounded LLVM disassembly slice."""

    status: str
    cache_key: str | None = None
    target_instruction_count: int = 0
    matched_instruction_count: int = 0
    mismatched_instruction_count: int = 0
    diagnostics: tuple[str, ...] = ()


def collect_llvm_targeted_cross_check(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    selected: tuple[OrbisFunctionSymbol, ...],
    instructions: dict[int, OrbisInstruction],
    invocations: list[OrbisToolInvocation],
) -> OrbisTargetedDisassemblyCrossCheck | None:
    """Run additive LLVM slices without promoting LLVM over Orbis output."""
    if context.llvm_objdump_path is None:
        return None
    help_result = _run_capability_probe(producer, context, invocations)
    if help_result.status != "observed":
        return _targeted_cross_check(
            context,
            invocations,
            status=help_result.status,
            diagnostics=help_result.diagnostics,
        )
    missing = _missing_capabilities(help_result.stdout, help_result.stderr)
    if missing:
        diagnostic = (
            "LLVM llvm-objdump does not advertise required target-slice options: "
            + ", ".join(missing)
        )
        _mark_profile_unsupported(invocations, "llvm-objdump-capability", diagnostic)
        return _targeted_cross_check(
            context,
            invocations,
            status="unsupported",
            diagnostics=(diagnostic,),
        )
    evidence = _collect_slices(producer, context, selected, instructions, invocations)
    return _targeted_summary(context, invocations, selected, evidence)


def _missing_capabilities(stdout: str, stderr: str) -> tuple[str, ...]:
    """Return required options absent from the executable's advertised help."""
    help_text = f"{stdout}\n{stderr}"
    missing: list[str] = []
    for option in LLVM_TARGET_CAPABILITY_FLAGS:
        pattern = rf"(?m)^\s*{re.escape(option)}(?:[=\s]|$)"
        if re.search(pattern, help_text) is None:
            missing.append(option)
    return tuple(missing)


def _run_capability_probe(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    invocations: list[OrbisToolInvocation],
):
    return producer._profile_executor.run_profile(
        context,
        "llvm-objdump-capability",
        ["--help"],
        invocations,
        executable=context.llvm_objdump_path,
        tool_identity=context.llvm_objdump_tool,
        requested_triple=context.llvm_target_triple,
    )


def _collect_slices(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    selected: tuple[OrbisFunctionSymbol, ...],
    instructions: dict[int, OrbisInstruction],
    invocations: list[OrbisToolInvocation],
) -> list[_TargetedSliceEvidence]:
    return [
        _run_targeted_slice(producer, context, symbol, instructions, invocations)
        for symbol in selected
    ]


def _targeted_summary(
    context: _ProductionContext,
    invocations: list[OrbisToolInvocation],
    selected: tuple[OrbisFunctionSymbol, ...],
    evidence: list[_TargetedSliceEvidence],
) -> OrbisTargetedDisassemblyCrossCheck:
    statuses = [item.status for item in evidence]
    target_count, matched_count, mismatched_count, observed_count = _evidence_counts(evidence)
    return OrbisTargetedDisassemblyCrossCheck(
        profile=LLVM_TARGET_PROFILE,
        requested_triple=context.llvm_target_triple,
        effective_triple=context.llvm_target_triple if "observed" in statuses else None,
        status=_targeted_status(statuses),
        slice_count=len(selected),
        observed_slice_count=observed_count,
        target_instruction_count=target_count,
        matched_instruction_count=matched_count,
        mismatched_instruction_count=mismatched_count,
        cache_keys=_cache_keys(evidence),
        diagnostics=_diagnostics(evidence),
    )


def _evidence_counts(
    evidence: list[_TargetedSliceEvidence],
) -> tuple[int, int, int, int]:
    return (
        sum(item.target_instruction_count for item in evidence),
        sum(item.matched_instruction_count for item in evidence),
        sum(item.mismatched_instruction_count for item in evidence),
        sum(item.status == "observed" for item in evidence),
    )


def _cache_keys(evidence: list[_TargetedSliceEvidence]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.cache_key for item in evidence if item.cache_key is not None))


def _diagnostics(evidence: list[_TargetedSliceEvidence]) -> tuple[str, ...]:
    return tuple(diagnostic for item in evidence for diagnostic in item.diagnostics)


def _run_targeted_slice(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    symbol: OrbisFunctionSymbol,
    instructions: dict[int, OrbisInstruction],
    invocations: list[OrbisToolInvocation],
) -> _TargetedSliceEvidence:
    result = producer._profile_executor.run_profile(
        context,
        LLVM_TARGET_PROFILE,
        _targeted_arguments(context, symbol),
        invocations,
        executable=context.llvm_objdump_path,
        tool_identity=context.llvm_objdump_tool,
        requested_triple=context.llvm_target_triple,
        effective_triple=context.llvm_target_triple,
        target_status="accepted",
        range_start=symbol.address,
        range_end=symbol.end_address,
    )
    invocation = _find_slice_invocation(invocations, symbol)
    if invocation is not None:
        _finalize_target_invocation(invocations, invocation, result.status, context)
    cache_key = invocation.cache_key if invocation is not None else None
    if result.status != "observed":
        return _TargetedSliceEvidence(
            status=result.status,
            cache_key=cache_key,
            diagnostics=result.diagnostics,
        )
    target_instructions = parse_instructions(result.stdout)
    expected, actual = _instruction_maps(symbol, instructions, target_instructions)
    matched = _matched_instruction_count(expected, actual)
    diagnostics = _slice_diagnostics(result.diagnostics, symbol, target_instructions)
    return _TargetedSliceEvidence(
        status=result.status,
        cache_key=cache_key,
        target_instruction_count=len(target_instructions),
        matched_instruction_count=matched,
        mismatched_instruction_count=len(set(expected) | set(actual)) - matched,
        diagnostics=diagnostics,
    )


def _targeted_arguments(context: _ProductionContext, symbol: OrbisFunctionSymbol) -> list[str]:
    return [
        f"--triple={context.llvm_target_triple}",
        *LLVM_TARGET_DISASSEMBLY_FLAGS,
        f"--start-address=0x{symbol.address:x}",
        f"--stop-address=0x{symbol.end_address:x}",
        str(context.elf_path),
    ]


def _find_slice_invocation(
    invocations: list[OrbisToolInvocation], symbol: OrbisFunctionSymbol
) -> OrbisToolInvocation | None:
    return next(
        (
            item
            for item in reversed(invocations)
            if item.profile == LLVM_TARGET_PROFILE
            and item.range_start == symbol.address
            and item.range_end == symbol.end_address
        ),
        None,
    )


def _instruction_maps(
    symbol: OrbisFunctionSymbol,
    instructions: dict[int, OrbisInstruction],
    target_instructions: tuple[OrbisInstruction, ...] | list[OrbisInstruction],
) -> tuple[dict[int, str], dict[int, str]]:
    expected = {
        address: instruction.raw_bytes
        for address, instruction in instructions.items()
        if symbol.address <= address < symbol.end_address
    }
    actual = {instruction.address: instruction.raw_bytes for instruction in target_instructions}
    return expected, actual


def _matched_instruction_count(expected: dict[int, str], actual: dict[int, str]) -> int:
    return sum(expected[address] == actual[address] for address in expected.keys() & actual.keys())


def _slice_diagnostics(
    diagnostics: tuple[str, ...],
    symbol: OrbisFunctionSymbol,
    target_instructions: tuple[OrbisInstruction, ...] | list[OrbisInstruction],
) -> tuple[str, ...]:
    if target_instructions:
        return diagnostics
    return (
        *diagnostics,
        f"LLVM target slice {symbol.address:#x}-{symbol.end_address:#x} had no decodable instructions",
    )


def _finalize_target_invocation(
    invocations: list[OrbisToolInvocation],
    invocation: OrbisToolInvocation,
    status: str,
    context: _ProductionContext,
) -> None:
    """Record whether the requested triple produced usable target output."""
    effective = context.llvm_target_triple if status == "observed" else None
    target_status = "observed" if status == "observed" else status
    for index in range(len(invocations) - 1, -1, -1):
        if invocations[index] == invocation:
            invocations[index] = replace(
                invocation,
                effective_triple=effective,
                target_status=target_status,
            )
            return


def _targeted_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_observed"
    if all(item in {"unavailable", "empty", "timeout"} for item in statuses):
        return statuses[0] if len(set(statuses)) == 1 else "unavailable"
    return "observed" if all(item == "observed" for item in statuses) else "partial"


def _targeted_cross_check(
    context: _ProductionContext,
    invocations: list[OrbisToolInvocation],
    *,
    status: str,
    diagnostics: tuple[str, ...],
) -> OrbisTargetedDisassemblyCrossCheck:
    return OrbisTargetedDisassemblyCrossCheck(
        profile=LLVM_TARGET_PROFILE,
        requested_triple=context.llvm_target_triple,
        effective_triple=None,
        status=status,
        diagnostics=diagnostics,
        cache_keys=tuple(
            item.cache_key
            for item in invocations
            if item.profile == "llvm-objdump-capability" and item.cache_key is not None
        ),
    )


def _mark_profile_unsupported(
    invocations: list[OrbisToolInvocation], profile: str, diagnostic: str
) -> None:
    for index in range(len(invocations) - 1, -1, -1):
        invocation = invocations[index]
        if invocation.profile == profile:
            invocations[index] = replace(
                invocation,
                status="unsupported",
                target_status="unsupported",
                diagnostics=(*invocation.diagnostics, diagnostic),
            )
            return


__all__ = ["collect_llvm_targeted_cross_check"]

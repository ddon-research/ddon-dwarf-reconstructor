"""DWARF-derived disassembly planning and conservative function association."""

from __future__ import annotations

from dataclasses import replace

from ...domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisInstruction,
)
from ...domain.models.disassembly_scope import DisassemblyRequest, DisassemblyTarget
from ...domain.models.implementation_evidence import (
    CodeRange,
    FunctionAssociationCandidate,
    FunctionMatchKind,
    ImplementationStatus,
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
)
from ..generation.runtime import GenerationRuntime


def build_disassembly_request(
    context: GenerationRuntime,
    root_symbol: str,
    methods: tuple[MethodAssemblyEvidence, ...],
) -> DisassemblyRequest:
    """Build a deterministic bounded scope from complete DWARF candidates."""
    targets: dict[str, DisassemblyTarget] = {}
    for method in methods:
        for candidate in method.candidates:
            ranges = _candidate_ranges(candidate.code_ranges)
            if not ranges:
                continue
            target_id = ":".join(
                (
                    method.owner,
                    method.method_name,
                    str(method.declaration_die_offset),
                    str(candidate.implementation_die_offset),
                )
            )
            targets[target_id] = DisassemblyTarget(
                target_id=target_id,
                declaration_die_offset=method.declaration_die_offset,
                implementation_die_offset=candidate.implementation_die_offset,
                declaration_cu_offset=method.declaration_cu_offset,
                implementation_cu_offset=candidate.implementation_cu_offset,
                ranges=ranges,
                range_provenance=tuple(item.source for item in candidate.code_ranges),
                qualified_name=f"{method.owner}::{method.method_name}",
                linkage_name=candidate.linkage_name,
                signature=method.signature,
            )
    return DisassemblyRequest(
        root_symbol=root_symbol,
        source_identity=source_sha256(context),
        targets=tuple(targets[key] for key in sorted(targets)),
    )


def attach_disassembly(
    method: MethodAssemblyEvidence,
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
) -> MethodAssemblyEvidence:
    """Attach every association candidate without promoting ambiguous evidence."""
    status, function, candidates, reasons = _association_details(
        method.implementation_status,
        method.candidates,
        disassembly,
        disassembly_error,
    )
    diagnostics = list(method.diagnostics)
    if FunctionMatchKind.SCOPE_MISSING in reasons:
        diagnostics.append("DWARF method target was absent from the bounded disassembly scope")
    name, address, size, instructions, raw_text = _function_fields(function)
    selected_offset = next(
        (
            candidate.implementation_die_offset
            for candidate in candidates
            if candidate.selected and candidate.implementation_die_offset is not None
        ),
        None,
    )
    return replace(
        method,
        assembly_status=status,
        selected_implementation_die_offset=(
            selected_offset if status is ImplementationStatus.MATCHED else None
        ),
        selected_function_name=name,
        selected_function_address=address,
        selected_function_size=size,
        instructions=instructions,
        raw_disassembly=raw_text,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        assembly_function_candidates=candidates,
        assembly_match_reasons=reasons,
    )


def source_sha256(context: GenerationRuntime) -> str | None:
    """Return the source identity supplied by the analytical query boundary."""
    query_port = context.class_parser.query_port
    if query_port is not None:
        return query_port.manifest.source_identity.sha256
    if context.source_hash is not None:
        return context.source_hash(context.elf_path)
    return None


def _candidate_ranges(ranges: tuple[CodeRange, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted({(item.start_address, item.end_address) for item in ranges}))


def _association_details(
    implementation_status: ImplementationStatus,
    candidates: tuple[MethodImplementationCandidate, ...],
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
) -> tuple[
    ImplementationStatus,
    OrbisFunctionDisassembly | None,
    tuple[FunctionAssociationCandidate, ...],
    tuple[FunctionMatchKind, ...],
]:
    if implementation_status is not ImplementationStatus.MATCHED:
        if implementation_status is ImplementationStatus.AMBIGUOUS:
            return _associate_ambiguous_candidates(candidates, disassembly, disassembly_error)
        return implementation_status, None, (), ()
    failure_status = _association_failure_status(disassembly, disassembly_error, candidates)
    if failure_status is not None:
        return failure_status, None, (), ()
    assert disassembly is not None
    return _associate_candidates(candidates, disassembly.functions)


def _associate_ambiguous_candidates(
    candidates: tuple[MethodImplementationCandidate, ...],
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
) -> tuple[
    ImplementationStatus,
    OrbisFunctionDisassembly | None,
    tuple[FunctionAssociationCandidate, ...],
    tuple[FunctionMatchKind, ...],
]:
    """Retain function evidence even when DWARF has multiple implementations."""
    if disassembly_error is not None or disassembly is None:
        return ImplementationStatus.AMBIGUOUS, None, (), (FunctionMatchKind.AMBIGUOUS,)
    status, function, function_candidates, reasons = _associate_candidates(
        candidates, disassembly.functions
    )
    del function
    del status
    return (
        ImplementationStatus.AMBIGUOUS,
        None,
        function_candidates,
        tuple(dict.fromkeys((*reasons, FunctionMatchKind.AMBIGUOUS))),
    )


def _associate_candidates(
    candidates: tuple[MethodImplementationCandidate, ...],
    functions: tuple[OrbisFunctionDisassembly, ...],
) -> tuple[
    ImplementationStatus,
    OrbisFunctionDisassembly | None,
    tuple[FunctionAssociationCandidate, ...],
    tuple[FunctionMatchKind, ...],
]:
    associations: list[
        tuple[MethodImplementationCandidate, OrbisFunctionDisassembly, FunctionMatchKind]
    ] = []
    reasons: list[FunctionMatchKind] = []
    for candidate in candidates:
        matches, match_kind = _matching_functions_with_kind(
            functions, candidate.code_ranges, candidate.linkage_name
        )
        reasons.append(match_kind)
        associations.extend((candidate, function, match_kind) for function in matches)
    function_candidates = tuple(
        FunctionAssociationCandidate(
            address=function.symbol.address,
            size=function.symbol.size,
            name=function.symbol.name,
            match_kind=match_kind,
            selected=len(associations) == 1,
            implementation_die_offset=candidate.implementation_die_offset,
        )
        for candidate, function, match_kind in associations
    )
    unique_functions = _unique_functions(associations)
    if len(associations) == 1 and len(unique_functions) == 1:
        return (
            ImplementationStatus.MATCHED,
            unique_functions[0],
            function_candidates,
            tuple(reasons),
        )
    if associations:
        return (
            ImplementationStatus.AMBIGUOUS,
            None,
            function_candidates,
            tuple(dict.fromkeys((*reasons, FunctionMatchKind.AMBIGUOUS))),
        )
    return ImplementationStatus.NOT_OBSERVED, None, (), (FunctionMatchKind.SCOPE_MISSING,)


def _unique_functions(
    associations: list[
        tuple[MethodImplementationCandidate, OrbisFunctionDisassembly, FunctionMatchKind]
    ],
) -> tuple[OrbisFunctionDisassembly, ...]:
    unique: dict[tuple[int, int, str], OrbisFunctionDisassembly] = {}
    for _candidate, function, _match_kind in associations:
        symbol = function.symbol
        unique[(symbol.address, symbol.size, symbol.name)] = function
    return tuple(unique.values())


def _association_failure_status(
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
    candidates: tuple[MethodImplementationCandidate, ...],
) -> ImplementationStatus | None:
    if disassembly_error is not None:
        if disassembly is None and disassembly_error == "Orbis disassembly was not requested":
            return ImplementationStatus.NOT_OBSERVED
        return ImplementationStatus.UNAVAILABLE
    if disassembly is None or not candidates:
        return ImplementationStatus.NOT_OBSERVED
    if disassembly.status == "unavailable" and not disassembly.functions:
        return ImplementationStatus.UNAVAILABLE
    return None


def _matching_functions_with_kind(
    functions: tuple[OrbisFunctionDisassembly, ...],
    ranges: tuple[CodeRange, ...],
    linkage_name: str | None,
) -> tuple[list[OrbisFunctionDisassembly], FunctionMatchKind]:
    exact = _range_start_matches(functions, ranges)
    if exact:
        return exact, FunctionMatchKind.RANGE_START
    contained = _contained_matches(functions, ranges)
    if contained:
        return contained, FunctionMatchKind.RANGE_CONTAINED
    named = _linkage_matches(functions, linkage_name)
    if named:
        return named, FunctionMatchKind.LINKAGE_NAME
    return [], FunctionMatchKind.SCOPE_MISSING


def _range_start_matches(
    functions: tuple[OrbisFunctionDisassembly, ...], ranges: tuple[CodeRange, ...]
) -> list[OrbisFunctionDisassembly]:
    return [
        function
        for function in functions
        if any(function.symbol.address == item.start_address for item in ranges)
    ]


def _contained_matches(
    functions: tuple[OrbisFunctionDisassembly, ...], ranges: tuple[CodeRange, ...]
) -> list[OrbisFunctionDisassembly]:
    return [
        function
        for function in functions
        if any(
            item.start_address <= function.symbol.address
            and function.symbol.end_address <= item.end_address
            for item in ranges
        )
    ]


def _linkage_matches(
    functions: tuple[OrbisFunctionDisassembly, ...], linkage_name: str | None
) -> list[OrbisFunctionDisassembly]:
    if not linkage_name:
        return []
    return [
        function
        for function in functions
        if function.symbol.name == linkage_name
        or function.symbol.name.startswith(f"{linkage_name}(")
    ]


def _function_fields(
    function: OrbisFunctionDisassembly | None,
) -> tuple[str | None, int | None, int | None, tuple[OrbisInstruction, ...], str]:
    if function is None:
        return None, None, None, (), ""
    return (
        function.symbol.name,
        function.symbol.address,
        function.symbol.size,
        function.instructions,
        function.raw_text,
    )


__all__ = ["attach_disassembly", "build_disassembly_request", "source_sha256"]

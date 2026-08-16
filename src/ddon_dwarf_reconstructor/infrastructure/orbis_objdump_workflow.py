"""Production workflow for one source-bound Orbis disassembly report."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from time import perf_counter
from typing import TYPE_CHECKING

from ..core.observability import get_logger, log_event
from ..domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisReference,
    OrbisRelocationEntry,
    OrbisStructuralCrossCheck,
    OrbisTargetedDisassemblyCrossCheck,
    OrbisToolInvocation,
)
from .orbis_objdump_profiles import (
    DISASSEMBLY_FLAGS,
    LLVM_METADATA_FLAGS,
    PARSER_VERSION,
    REPORT_SCHEMA_VERSION,
    STANDARD_RELOCATION_FLAGS,
    SYMBOL_FALLBACK_FLAGS,
    SYMBOL_FLAGS,
)
from .orbis_objdump_targeted import collect_llvm_targeted_cross_check
from .orbis_sce_metadata import OrbisSceMetadataReader, SceMetadataReadResult

if TYPE_CHECKING:
    from .orbis_objdump import OrbisObjdumpProducer, _ProductionContext

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _AdditionalEvidence:
    standard_relocations: tuple[OrbisReference, ...]
    sce_metadata: SceMetadataReadResult
    llvm_cross_check: OrbisStructuralCrossCheck | None
    llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None


def produce_uncached(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    started_at: float,
) -> OrbisDisassemblyReport:
    """Run all retained profiles and publish the parsed report to the cache."""
    invocations: list[OrbisToolInvocation] = []
    selected = _select_symbols(producer, context, invocations)
    if not selected:
        report = producer._empty_report(
            context,
            invocations,
            (f"No Orbis function symbols found for {context.root_symbol}",),
        )
        producer._write_cached(context.cache_path, report)
        return report

    instructions, range_outputs = _collect_ranges(producer, context, selected, invocations)
    additional = _collect_additional_profiles(
        producer,
        context,
        selected,
        instructions,
        invocations,
    )
    report = _build_report(
        producer,
        context,
        selected,
        instructions,
        range_outputs,
        additional,
        invocations,
    )
    producer._write_cached(context.cache_path, report)
    producer.last_cache_hit = False
    log_event(
        logger,
        logging.INFO,
        "orbis_disassembly_completed",
        root_symbol=context.root_symbol,
        function_count=len(report.functions),
        instruction_count=len(instructions),
        cache_path=context.cache_path,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )
    return report


def _select_symbols(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    invocations: list[OrbisToolInvocation],
) -> tuple[OrbisFunctionSymbol, ...]:
    result = producer._run_profile(
        context,
        "symbols",
        [*SYMBOL_FLAGS, str(context.elf_path)],
        invocations,
    )
    symbols = producer.parse_symbols(result.stdout)
    selected = _select_for_context(producer, symbols, context)
    if not selected and (result.status != "observed" or not symbols):
        fallback = producer._run_profile(
            context,
            "symbols-fallback",
            [*SYMBOL_FALLBACK_FLAGS, str(context.elf_path)],
            invocations,
        )
        symbols = producer.parse_symbols(fallback.stdout)
        selected = _select_for_context(producer, symbols, context)
    log_event(
        logger,
        logging.DEBUG,
        "orbis_disassembly_symbols_selected",
        root_symbol=context.root_symbol,
        symbol_count=len(selected),
    )
    return selected


def _select_for_context(
    producer: OrbisObjdumpProducer,
    symbols: tuple[OrbisFunctionSymbol, ...],
    context: _ProductionContext,
) -> tuple[OrbisFunctionSymbol, ...]:
    if context.scope_policy == "root-prefix-v1":
        return producer.select_root_symbols(symbols, context.root_symbol)
    return producer.select_target_symbols(symbols, context.targets)


def _collect_ranges(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    selected: tuple[OrbisFunctionSymbol, ...],
    invocations: list[OrbisToolInvocation],
) -> tuple[dict[int, OrbisInstruction], list[tuple[int, int, str]]]:
    instructions: dict[int, OrbisInstruction] = {}
    range_outputs: list[tuple[int, int, str]] = []
    ranges = producer._group_ranges(selected)
    log_event(
        logger,
        logging.DEBUG,
        "orbis_disassembly_ranges_selected",
        root_symbol=context.root_symbol,
        symbol_count=len(selected),
        range_count=len(ranges),
    )
    for start_address, stop_address in ranges:
        range_arguments = [
            *DISASSEMBLY_FLAGS,
            f"--start-address=0x{start_address:x}",
            f"--stop-address=0x{stop_address:x}",
            str(context.elf_path),
        ]
        result = producer._run_profile(context, "disassembly", range_arguments, invocations)
        range_outputs.append((start_address, stop_address, result.stdout))
        for instruction in producer.parse_instructions(result.stdout):
            instructions[instruction.address] = instruction
    return instructions, range_outputs


def _collect_additional_profiles(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    selected: tuple[OrbisFunctionSymbol, ...],
    instructions: dict[int, OrbisInstruction],
    invocations: list[OrbisToolInvocation],
) -> _AdditionalEvidence:
    standard_result = producer._run_profile(
        context,
        "standard-relocations",
        [*STANDARD_RELOCATION_FLAGS, str(context.elf_path)],
        invocations,
    )
    relocations = producer.parse_relocations(standard_result.stdout)
    if not relocations and standard_result.status == "observed":
        _mark_profile_empty(invocations, "standard-relocations")
    sce_metadata = OrbisSceMetadataReader().read(
        context.elf_path,
        source_sha256=context.elf_sha256,
        tool=context.tool,
        cache_dir=producer._shared_profile_dir(context),
        sdk_definition_identity=context.sdk_definition_identity,
        relevant_ranges=_relevant_relocation_ranges(selected, instructions),
    )
    llvm_cross_check = _collect_llvm_cross_check(producer, context, invocations)
    llvm_targeted_cross_check = collect_llvm_targeted_cross_check(
        producer,
        context,
        selected,
        instructions,
        invocations,
    )
    return _AdditionalEvidence(
        relocations,
        sce_metadata,
        llvm_cross_check,
        llvm_targeted_cross_check,
    )


def _relevant_relocation_ranges(
    selected: tuple[OrbisFunctionSymbol, ...],
    instructions: dict[int, OrbisInstruction],
) -> tuple[tuple[int, int], ...]:
    """Select code and referenced addresses for the report projection.

    SCE relocation offsets can identify an instruction, a GOT slot, or another
    data location named by an operand. Restricting the reader to function
    ranges alone silently drops the latter two categories. A one-byte range
    preserves the exact referenced address without widening to a data section.
    """
    ranges = {(item.address, item.end_address) for item in selected}
    for instruction in instructions.values():
        for reference in instruction.references:
            if reference.address is not None:
                ranges.add((reference.address, reference.address + 1))
    return tuple(sorted(ranges))


def _mark_profile_empty(invocations: list[OrbisToolInvocation], profile: str) -> None:
    for index in range(len(invocations) - 1, -1, -1):
        invocation = invocations[index]
        if invocation.profile == profile and invocation.status == "observed":
            invocations[index] = replace(invocation, status="empty")
            return


def _collect_llvm_cross_check(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    invocations: list[OrbisToolInvocation],
) -> OrbisStructuralCrossCheck | None:
    if context.llvm_readobj_path is None:
        return None
    result = producer._run_profile(
        context,
        "llvm-elf-metadata-json",
        [*LLVM_METADATA_FLAGS, str(context.elf_path)],
        invocations,
        executable=context.llvm_readobj_path,
        tool_identity=context.llvm_tool,
    )
    diagnostics = list(result.diagnostics)
    unknown_tags: tuple[int, ...] = ()
    status = result.status
    if result.stdout:
        try:
            unknown_tags, parse_diagnostics = producer.parse_llvm_metadata(result.stdout)
            diagnostics.extend(parse_diagnostics)
            if parse_diagnostics:
                status = "partial"
        except ValueError as error:
            status = "partial"
            diagnostics.append(str(error))
    invocation = next(
        (item for item in reversed(invocations) if item.profile == "llvm-elf-metadata-json"),
        None,
    )
    return OrbisStructuralCrossCheck(
        profile="llvm-elf-metadata-json",
        status=status,
        output_path=invocation.stdout_path if invocation else None,
        output_sha256=invocation.stdout_sha256 if invocation else None,
        unknown_dynamic_tags=unknown_tags,
        diagnostics=tuple(diagnostics),
        requested_triple=context.llvm_target_triple,
        target_status="not_applicable",
    )


def _build_report(
    producer: OrbisObjdumpProducer,
    context: _ProductionContext,
    selected: tuple[OrbisFunctionSymbol, ...],
    instructions: dict[int, OrbisInstruction],
    range_outputs: list[tuple[int, int, str]],
    additional: _AdditionalEvidence,
    invocations: list[OrbisToolInvocation],
) -> OrbisDisassemblyReport:
    functions = tuple(
        OrbisFunctionDisassembly(
            symbol=symbol,
            instructions=tuple(
                instructions[address]
                for address in sorted(instructions)
                if symbol.address <= address < symbol.end_address
            ),
            raw_text=producer._raw_function_text(range_outputs, symbol),
        )
        for symbol in selected
    )
    functions, relocation_entries = _link_relocations(
        functions,
        additional.sce_metadata.relocation_entries,
    )
    diagnostics = tuple(
        diagnostic for invocation in invocations for diagnostic in invocation.diagnostics
    )
    statuses = {invocation.status for invocation in invocations}
    if additional.sce_metadata.status not in {"observed"}:
        statuses.add(additional.sce_metadata.status)
    return OrbisDisassemblyReport(
        artifact_key=context.artifact_key,
        build_root=context.root_symbol,
        elf_sha256=context.elf_sha256,
        tool=context.tool,
        flags=DISASSEMBLY_FLAGS,
        parser_version=PARSER_VERSION,
        functions=functions,
        schema_version=REPORT_SCHEMA_VERSION,
        invocations=tuple(invocations),
        relocations=additional.standard_relocations,
        dynamic_tags=additional.sce_metadata.dynamic_tags,
        sce_segments=additional.sce_metadata.sce_segments,
        relocation_tables=additional.sce_metadata.relocation_tables,
        relocation_entries=relocation_entries,
        relocation_cache_path=additional.sce_metadata.cache_path,
        relocation_cache_sha256=additional.sce_metadata.cache_sha256,
        relocation_cache_entry_count=additional.sce_metadata.cache_entry_count,
        sce_metadata_status=additional.sce_metadata.status,
        sce_metadata_diagnostics=additional.sce_metadata.diagnostics,
        llvm_cross_check=additional.llvm_cross_check,
        llvm_targeted_cross_check=additional.llvm_targeted_cross_check,
        sdk_definition_identity=context.sdk_definition_identity,
        diagnostics=tuple((*diagnostics, *additional.sce_metadata.diagnostics)),
        status="partial" if statuses - {"observed"} else "observed",
        scope_hash=context.scope_hash,
        scope_policy=context.scope_policy,
        target_count=context.target_count,
    )


def _link_relocations(
    functions: tuple[OrbisFunctionDisassembly, ...],
    entries: tuple[OrbisRelocationEntry, ...],
) -> tuple[tuple[OrbisFunctionDisassembly, ...], tuple[OrbisRelocationEntry, ...]]:
    """Attach method-range SCE records to instruction references without copying them."""
    by_offset = _relocations_by_offset(entries)
    linked_addresses: dict[str, set[int]] = {entry.relocation_id: set() for entry in entries}
    linked_functions = tuple(
        _link_function(function, by_offset, linked_addresses) for function in functions
    )
    linked_entries = tuple(
        replace(entry, instruction_addresses=tuple(sorted(linked_addresses[entry.relocation_id])))
        for entry in entries
    )
    return linked_functions, linked_entries


def _relocations_by_offset(
    entries: tuple[OrbisRelocationEntry, ...],
) -> dict[int, list[OrbisRelocationEntry]]:
    by_offset: dict[int, list[OrbisRelocationEntry]] = {}
    for entry in entries:
        by_offset.setdefault(entry.offset, []).append(entry)
    return by_offset


def _link_function(
    function: OrbisFunctionDisassembly,
    by_offset: dict[int, list[OrbisRelocationEntry]],
    linked_addresses: dict[str, set[int]],
) -> OrbisFunctionDisassembly:
    instructions = tuple(
        _link_instruction(instruction, by_offset, linked_addresses)
        for instruction in function.instructions
    )
    return replace(function, instructions=instructions)


def _link_instruction(
    instruction: OrbisInstruction,
    by_offset: dict[int, list[OrbisRelocationEntry]],
    linked_addresses: dict[str, set[int]],
) -> OrbisInstruction:
    matches = list(by_offset.get(instruction.address, ()))
    references: list[OrbisReference] = []
    for reference in instruction.references:
        reference_matches = (
            by_offset.get(reference.address, ()) if reference.address is not None else ()
        )
        if reference_matches:
            matches.extend(reference_matches)
            reference = replace(reference, relocation_id=reference_matches[0].relocation_id)
        references.append(reference)
    for entry in {item.relocation_id: item for item in matches}.values():
        linked_addresses[entry.relocation_id].add(instruction.address)
    return replace(instruction, references=tuple(references))

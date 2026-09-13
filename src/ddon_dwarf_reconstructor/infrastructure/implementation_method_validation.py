"""Per-method evidence assembly for the implementation validator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..domain.models.disassembly import OrbisInstruction, OrbisReference
from ..domain.models.implementation_context import MethodContextPacket
from ..domain.models.implementation_validation import (
    AbiEvidence,
    CompilerEvidence,
    MethodValidationEvidence,
    SemanticParity,
    ValidationStatus,
)
from ..domain.services.cpp_reconstruction.control_flow import normalize_parity as _normalize_parity
from ..domain.services.cpp_reconstruction.instruction_effects import analyze_instruction_effects
from .implementation_abi_probes import aggregate_probe_status
from .implementation_cfi import inspect_cfi
from .implementation_dwarf_context import dwarf_method_evidence, store_cfi_status
from .implementation_nids import NidIndex
from .implementation_relocations import RelocationIndex
from .implementation_toolchain import emit_and_assemble_method
from .orbis_sdk_definitions import DEFAULT_PS4_LLVM_TRIPLE


def validate_method(
    raw: dict[str, Any],
    index: int,
    source: Path,
    output_dir: Path,
    sce_status: str,
    relocations: tuple[Any, ...] | RelocationIndex,
    nids: tuple[Any, ...] | NidIndex,
    abi_probes: tuple[CompilerEvidence, ...],
    assembler: Path | None,
    readelf: Path | None,
    store: Any | None,
    objdump: Path | None = None,
    linker: Path | None = None,
    timeout_seconds: float | None = None,
    assembly_profile: str = "byte-replay",
) -> tuple[MethodValidationEvidence, CompilerEvidence]:
    """Build one method evidence record from independent source-bound dimensions."""
    instructions, address, size, end = _method_inputs(raw)
    effects = analyze_instruction_effects(instructions)
    locations, facts, cfi_records, store_diagnostics = dwarf_method_evidence(
        store, raw, address, end
    )
    cfi = _method_cfi(source, store, address, size, end, cfi_records, store_diagnostics)
    effects = _apply_cfi_gate(effects, cfi)
    abi = _abi_evidence(raw, cfi, abi_probes, facts)
    selected_relocations, relocation_status = _relocation_evidence(
        relocations, address, end, sce_status
    )
    selected_nids, nid_status = _nid_evidence(nids, selected_relocations)
    method_id = _method_id(raw, index)
    compiler, parity, artifacts = _emit_method(
        method_id,
        instructions,
        output_dir,
        assembler,
        readelf,
        objdump,
        effects.status,
        relocation_status,
        nid_status,
        linker,
        timeout_seconds,
        assembly_profile,
        (address, size),
    )
    parity = _method_parity(parity, compiler, relocation_status, nid_status, abi.status)
    context = _context_packet(
        raw,
        instructions,
        cfi,
        selected_relocations,
        selected_nids,
        locations=locations,
        cfi_records=cfi_records,
        abi_facts=facts,
        diagnostics=store_diagnostics,
    )
    diagnostics = _method_diagnostics(raw, instructions, abi)
    method = MethodValidationEvidence(
        method_id=method_id,
        method_name=_method_name(raw),
        function_address=address,
        function_size=size,
        context=context,
        relocation_status=relocation_status,
        nid_status=nid_status,
        abi=abi,
        effects=effects,
        compiler=compiler,
        parity=parity,
        artifacts=artifacts,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )
    return method, compiler


def _method_inputs(
    raw: dict[str, Any],
) -> tuple[tuple[OrbisInstruction, ...], int | None, int | None, int | None]:
    instructions = _instructions(raw.get("instructions"))
    address = _optional_int(raw.get("selected_function_address"))
    size = _optional_int(raw.get("selected_function_size"))
    end = _method_interval_end(address, size)
    return instructions, address, size, end


def _method_interval_end(address: int | None, size: int | None) -> int | None:
    """Return a selected function end only when its arithmetic is safe."""
    maximum = 1 << 64
    if (
        address is None
        or size is None
        or isinstance(address, bool)
        or isinstance(size, bool)
        or not 0 <= address < maximum
        or size <= 0
    ):
        return None
    end = address + size
    return end if end < maximum - 1 else None


def _method_cfi(
    source: Path,
    store: Any | None,
    address: int | None,
    size: int | None,
    end: int | None,
    cfi_records: tuple[dict[str, object], ...],
    diagnostics: tuple[str, ...],
) -> Any:
    if store is not None and address is not None and end is not None:
        return store_cfi_status(cfi_records, diagnostics)
    if address is not None and size is not None:
        return inspect_cfi(source, address, size)
    return None


def _apply_cfi_gate(effects: Any, cfi: Any) -> Any:
    if cfi is None or cfi.status is ValidationStatus.OBSERVED:
        return effects
    status = (
        ValidationStatus.PARTIAL if effects.status is ValidationStatus.OBSERVED else effects.status
    )
    return replace(
        effects,
        status=status,
        diagnostics=tuple(effects.diagnostics) + ("CFI does not independently cover this method",),
    )


def _relocation_evidence(
    relocations: tuple[Any, ...] | RelocationIndex,
    address: int | None,
    end: int | None,
    sce_status: str,
) -> tuple[tuple[Any, ...], ValidationStatus]:
    selected = _select_relocations(relocations, address, end)
    empty_status = (
        ValidationStatus.OBSERVED
        if not selected and address is not None and end is not None and sce_status == "observed"
        else ValidationStatus.NOT_OBSERVED
    )
    return selected, dimension_status(tuple(item.status for item in selected), empty_status)


def _select_relocations(
    relocations: tuple[Any, ...] | RelocationIndex,
    address: int | None,
    end: int | None,
) -> tuple[Any, ...]:
    if isinstance(relocations, RelocationIndex):
        return relocations.select(address, end)
    if address is None or end is None:
        return ()
    return tuple(item for item in relocations if address <= item.relocation_offset < end)


def _nid_evidence(
    nids: tuple[Any, ...] | NidIndex, selected_relocations: tuple[Any, ...]
) -> tuple[tuple[Any, ...], ValidationStatus]:
    selected_ids = {item.relocation_id for item in selected_relocations}
    selected = (
        nids.select(selected_relocations)
        if isinstance(nids, NidIndex)
        else tuple(item for item in nids if item.relocation_id in selected_ids)
    )
    empty_status = ValidationStatus.OBSERVED if not selected_ids else ValidationStatus.NOT_OBSERVED
    return selected, dimension_status(tuple(item.status for item in selected), empty_status)


def _emit_method(
    method_id: str,
    instructions: tuple[OrbisInstruction, ...],
    output_dir: Path,
    assembler: Path | None,
    readelf: Path | None,
    objdump: Path | None,
    effect_status: ValidationStatus,
    relocation_status: ValidationStatus,
    nid_status: ValidationStatus,
    linker: Path | None = None,
    timeout_seconds: float | None = None,
    assembly_profile: str = "byte-replay",
    expected_range: tuple[int | None, int | None] = (None, None),
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    assembly_ready = all(
        (
            bool(instructions),
            relocation_status is ValidationStatus.OBSERVED,
            nid_status is ValidationStatus.OBSERVED,
            effect_status is ValidationStatus.OBSERVED,
        )
    )
    return emit_and_assemble_method(
        method_id,
        instructions,
        output_dir,
        assembler,
        effect_status=effect_status,
        readelf=readelf,
        objdump=objdump,
        linker=linker,
        assembly_ready=assembly_ready,
        timeout_seconds=timeout_seconds,
        assembly_profile=assembly_profile,
        expected_start=expected_range[0],
        expected_size=expected_range[1],
    )


def _method_parity(
    parity: SemanticParity,
    compiler: CompilerEvidence,
    relocation: ValidationStatus,
    nid: ValidationStatus,
    abi: ValidationStatus,
) -> SemanticParity:
    return _normalize_parity(
        parity,
        compiler.status,
        compiler_evidence=compiler,
        required_dimensions=(
            ("relocation", relocation),
            ("NID/import/export", nid),
            ("ABI/CFI", abi),
        ),
    )


def _method_diagnostics(
    raw: dict[str, Any], instructions: tuple[OrbisInstruction, ...], abi: AbiEvidence
) -> list[str]:
    diagnostics = [str(item) for item in _list_value(raw.get("diagnostics"))]
    address = _optional_int(raw.get("selected_function_address"))
    size = _optional_int(raw.get("selected_function_size"))
    if address is not None and size is not None and _method_interval_end(address, size) is None:
        diagnostics.append("selected ELF function range is outside the 64-bit address domain")
    if not instructions:
        diagnostics.append("method has no decoded instruction evidence")
    if abi.status is not ValidationStatus.OBSERVED:
        diagnostics.append(
            "ABI evidence is not complete; parameter and return locations are not source-bound"
        )
    return diagnostics


def _context_packet(
    raw: dict[str, Any],
    instructions: tuple[OrbisInstruction, ...],
    cfi: Any,
    relocations: tuple[Any, ...],
    nids: tuple[Any, ...],
    *,
    locations: tuple[dict[str, object], ...] = (),
    cfi_records: tuple[dict[str, object], ...] = (),
    abi_facts: dict[str, Any] | None = None,
    diagnostics: tuple[str, ...] = (),
) -> MethodContextPacket:
    context_diagnostics = list(diagnostics)
    ranges = _context_ranges(raw)
    locations = _context_locations(raw, locations, context_diagnostics)
    cfi_records = _context_cfi(cfi, cfi_records, context_diagnostics)
    return MethodContextPacket(
        declaration_die_offset=_optional_int(raw.get("declaration_die_offset")),
        implementation_die_offset=_optional_int(raw.get("selected_implementation_die_offset")),
        declaration_cu_offset=_optional_int(raw.get("declaration_cu_offset")),
        implementation_cu_offset=_implementation_cu_offset(raw),
        code_ranges=tuple(dict.fromkeys(ranges)),
        locations=locations,
        cfi=cfi_records,
        disassembly_addresses=tuple(item.address for item in instructions),
        relocation_ids=tuple(item.relocation_id for item in relocations),
        nid_ids=tuple(
            str(item.encoded_nid or item.encoded_symbol)
            for item in nids
            if item.encoded_nid is not None or item.encoded_symbol is not None
        ),
        abi_facts=dict(abi_facts or {}),
        diagnostics=tuple(context_diagnostics),
    )


def _context_ranges(raw: dict[str, Any]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for candidate in _list_value(raw.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        ranges.extend(_candidate_ranges(candidate))
    return ranges


def _candidate_ranges(candidate: dict[str, Any]) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for value in _list_value(candidate.get("code_ranges")):
        if not isinstance(value, dict):
            continue
        start = _optional_int(value.get("start_address"))
        end = _optional_int(value.get("end_address"))
        if start is not None and end is not None and end > start:
            result.append((start, end, str(value.get("source", "DWARF"))))
    return result


def _context_locations(
    raw: dict[str, Any],
    locations: tuple[dict[str, object], ...],
    diagnostics: list[str],
) -> tuple[dict[str, object], ...]:
    if locations:
        return locations
    fallback = tuple(
        value for value in _list_value(raw.get("locations")) if isinstance(value, dict)
    )
    if not fallback:
        diagnostics.append(
            "parameter/object location records were not present in the discovery report"
        )
    return fallback


def _context_cfi(
    cfi: Any, cfi_records: tuple[dict[str, object], ...], diagnostics: list[str]
) -> tuple[dict[str, object], ...]:
    if not cfi_records and cfi is not None:
        return (
            {
                "status": cfi.status.value,
                "diagnostics": list(cfi.diagnostics),
                "details": dict(cfi.details),
            },
        )
    if not cfi_records:
        diagnostics.append("CFI was not inspected because the method range is incomplete")
    return cfi_records


def _abi_evidence(
    raw: dict[str, Any],
    cfi: Any,
    probes: tuple[CompilerEvidence, ...],
    dwarf_facts: dict[str, Any] | None = None,
) -> AbiEvidence:
    facts = dwarf_facts or {}
    cfi_status = cfi.status if cfi is not None else ValidationStatus.NOT_OBSERVED
    return AbiEvidence(
        status=_abi_status(cfi_status, probes, facts),
        target_triple=DEFAULT_PS4_LLVM_TRIPLE,
        calling_convention=_fact_string(facts, raw, "calling_convention"),
        object_pointer=_fact_string(facts, raw, "object_pointer"),
        parameter_locations=_fact_values(facts, raw, "parameter_locations"),
        hidden_parameters=tuple(str(item) for item in facts.get("hidden_parameters", ())),
        artificial_parameters=tuple(str(item) for item in facts.get("artificial_parameters", ())),
        frame_base_locations=tuple(str(item) for item in facts.get("frame_base_locations", ())),
        return_location=_fact_string(facts, raw, "return_location"),
        hidden_return=_hidden_return(facts, raw),
        cfi_status=cfi_status,
        diagnostics=_abi_diagnostics(cfi, facts, cfi_status),
    )


def _abi_status(
    cfi_status: ValidationStatus,
    probes: tuple[CompilerEvidence, ...],
    facts: dict[str, Any],
) -> ValidationStatus:
    probe_status = aggregate_probe_status(probes)
    if probe_status is ValidationStatus.FAILED or cfi_status is ValidationStatus.FAILED:
        return ValidationStatus.FAILED
    if cfi_status in {ValidationStatus.UNAVAILABLE, ValidationStatus.BLOCKED}:
        return cfi_status
    missing = _abi_missing_facts(cfi_status, facts)
    if not facts and probe_status is ValidationStatus.NOT_OBSERVED:
        return ValidationStatus.NOT_OBSERVED
    return ValidationStatus.OBSERVED if not missing else ValidationStatus.PARTIAL


def _abi_diagnostics(
    cfi: Any, facts: dict[str, Any], cfi_status: ValidationStatus
) -> tuple[str, ...]:
    diagnostics = list(cfi.diagnostics if cfi is not None else ("CFI was not inspected",))
    diagnostics.extend(str(item) for item in facts.get("diagnostics", ()))
    diagnostics.append("compiler probes do not replace method-specific DWARF parameter locations")
    missing = _abi_missing_facts(cfi_status, facts)
    if missing:
        diagnostics.append("ABI completeness missing: " + ", ".join(missing))
    return tuple(dict.fromkeys(diagnostics))


def _abi_missing_facts(cfi_status: ValidationStatus, facts: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    if not facts.get("calling_convention"):
        missing.append("calling convention")
    missing.extend(_missing_object_pointer(facts))
    missing.extend(_missing_parameter_locations(facts))
    missing.extend(_missing_return_facts(cfi_status, facts))
    return tuple(dict.fromkeys(missing))


def _missing_object_pointer(facts: dict[str, Any]) -> tuple[str, ...]:
    required = bool(facts.get("object_pointer_required", facts.get("object_pointer")))
    return ("object pointer location",) if required and not facts.get("object_pointer") else ()


def _missing_parameter_locations(facts: dict[str, Any]) -> tuple[str, ...]:
    formal_count = facts.get("formal_parameter_count")
    located_count = facts.get("located_parameter_count")
    if isinstance(formal_count, int) and isinstance(located_count, int):
        if formal_count != located_count:
            return ("complete parameter locations",)
    elif not facts.get("parameter_locations") and formal_count != 0:
        return ("parameter locations",)
    return ()


def _missing_return_facts(cfi_status: ValidationStatus, facts: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    if not facts.get("frame_base_locations"):
        missing.append("frame base location")
    return_type_status = facts.get("return_type_status")
    if return_type_status is not None and return_type_status is not ValidationStatus.OBSERVED:
        missing.append("source return type")
    if not facts.get("return_location"):
        missing.append("return location")
    if cfi_status is not ValidationStatus.OBSERVED:
        missing.append("complete CFI coverage")
    return tuple(dict.fromkeys(missing))


def _fact_string(facts: dict[str, Any], raw: dict[str, Any], key: str) -> str | None:
    return _optional_string(facts.get(key)) or _optional_string(raw.get(key))


def _fact_values(facts: dict[str, Any], raw: dict[str, Any], key: str) -> tuple[str, ...]:
    values = tuple(str(item) for item in facts.get(key, ()))
    return values or tuple(str(item) for item in _list_value(raw.get(key)))


def _hidden_return(facts: dict[str, Any], raw: dict[str, Any]) -> bool | None:
    fact = facts.get("hidden_return")
    if isinstance(fact, bool):
        return fact
    value = raw.get("hidden_return")
    return value if isinstance(value, bool) else None


def dimension_status(
    statuses: tuple[ValidationStatus, ...], empty: ValidationStatus
) -> ValidationStatus:
    """Collapse per-record evidence without promoting incomplete dimensions."""
    if not statuses:
        return empty
    for status in (
        ValidationStatus.FAILED,
        ValidationStatus.BLOCKED,
        ValidationStatus.UNAVAILABLE,
        ValidationStatus.NOT_OBSERVED,
        ValidationStatus.PARTIAL,
    ):
        if status in statuses:
            return status
    return ValidationStatus.OBSERVED


def _instructions(value: object) -> tuple[OrbisInstruction, ...]:
    return tuple(_instruction(item) for item in _list_value(value) if isinstance(item, dict))


def _instruction(item: dict[str, Any]) -> OrbisInstruction:
    return OrbisInstruction(
        address=_int_value(item.get("address")),
        raw_bytes=str(item.get("raw_bytes", "")),
        mnemonic=str(item.get("mnemonic", "")),
        operands=str(item.get("operands", "")),
        source_file=_optional_string(item.get("source_file")),
        source_line=_optional_int(item.get("source_line")),
        call_target_address=_optional_int(item.get("call_target_address")),
        call_target_name=_optional_string(item.get("call_target_name")),
        references=tuple(
            _reference(value)
            for value in _list_value(item.get("references"))
            if isinstance(value, dict)
        ),
    )


def _reference(item: dict[str, Any]) -> OrbisReference:
    return OrbisReference(
        kind=str(item.get("kind", "unknown")),
        address=_optional_int(item.get("address")),
        resolved_name=_optional_string(item.get("resolved_name")),
        raw_operand=str(item.get("raw_operand", "")),
        resolution_status=str(item.get("resolution_status", "unresolved")),
        relocation=_optional_string(item.get("relocation")),
        relocation_id=_optional_string(item.get("relocation_id")),
    )


def _method_id(raw: dict[str, Any], index: int) -> str:
    source_artifact = raw.get("source_artifact")
    if isinstance(source_artifact, dict) and source_artifact.get("method_id"):
        return str(source_artifact["method_id"])
    payload = json.dumps(
        {
            "owner": raw.get("owner"),
            "method_name": raw.get("method_name"),
            "signature": raw.get("signature"),
            "address": raw.get("selected_function_address"),
            "index": index,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def _method_name(raw: dict[str, Any]) -> str:
    owner = str(raw.get("owner", ""))
    name = str(raw.get("method_name", ""))
    return f"{owner}::{name}" if owner else name


def _implementation_cu_offset(raw: dict[str, Any]) -> int | None:
    candidates = _list_value(raw.get("candidates"))
    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    return _optional_int(candidate.get("implementation_cu_offset"))


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    return 0


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return _int_value(value)
    except TypeError, ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _list_value(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = ["dimension_status", "validate_method"]

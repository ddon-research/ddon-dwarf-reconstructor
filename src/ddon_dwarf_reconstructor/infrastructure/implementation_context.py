"""Deterministic per-method context packets for assembly transformation agents."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.disassembly import OrbisInstruction
from ..domain.models.implementation_evidence import (
    ArtifactDescriptor,
    ImplementationDiscoveryReport,
    MethodAssemblyEvidence,
)
from ..domain.models.implementation_validation import (
    MethodContextPacket,
    MethodValidationEvidence,
    ValidationStatus,
)

CONTEXT_SCHEMA_VERSION = "implementation-context/1.0"
_NOT_OBSERVED = ValidationStatus.NOT_OBSERVED.value


def normalize_raw_assembly(value: str) -> str:
    """Normalize tool text for a stable evidence file without adding metadata."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


def render_context_packet(
    method: MethodAssemblyEvidence,
    method_id: str,
    report: ImplementationDiscoveryReport,
    descriptors: tuple[ArtifactDescriptor, ...],
    *,
    validation: MethodValidationEvidence | None = None,
    assembler: Path | None = None,
    object_content: bytes | None = None,
) -> str:
    """Serialize one bounded context packet with stable JSON ordering."""
    payload = build_context_packet(
        method,
        method_id,
        report,
        descriptors,
        validation=validation,
        assembler=assembler,
        object_content=object_content,
    )
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def build_context_packet(
    method: MethodAssemblyEvidence,
    method_id: str,
    report: ImplementationDiscoveryReport,
    descriptors: tuple[ArtifactDescriptor, ...],
    *,
    validation: MethodValidationEvidence | None = None,
    assembler: Path | None = None,
    object_content: bytes | None = None,
) -> dict[str, object]:
    """Build the agent-facing join without duplicating raw disassembly text."""
    context = (
        validation.context
        if validation is not None
        else method.dwarf_context or _default_context(method)
    )
    validation_payload = _validation_payload(validation)
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "method_id": method_id,
        "identity": _identity_payload(method),
        "source_binding": _source_binding(report),
        "address_policy": {
            "policy": "elf-link-time-zero-bias",
            "load_bias": 0,
            "status": _NOT_OBSERVED,
            "scope_policy": report.disassembly_scope_policy,
        },
        "ranges": _range_payload(method),
        "function": {
            "name": method.selected_function_name,
            "address": method.selected_function_address,
            "size": method.selected_function_size,
            "end": _function_end(method),
        },
        "instructions": [_instruction_payload(item) for item in method.instructions],
        "references": _reference_payload(method),
        "control_flow": _control_flow_payload(method),
        "dwarf_context": context.to_dict(),
        "relocations": _relocation_payload(method, report, validation),
        "nids": _nid_payload(validation),
        "abi": _abi_payload(method, validation),
        "instruction_effects": _dimension_payload(validation, "effects"),
        "compiler": _compiler_payload(
            validation,
            report,
            descriptors,
            assembler=assembler,
            object_content=object_content,
        ),
        "semantic_parity": _dimension_payload(validation, "parity"),
        "transformation_cues": _transformation_cues(method, validation),
        "evidence_status": _evidence_status(method, descriptors, validation),
        "artifacts": [item.to_dict() for item in descriptors],
        "tool_evidence": _tool_evidence(report),
        "diagnostics": list(dict.fromkeys(method.diagnostics + context.diagnostics)),
        "validation": validation_payload,
    }


def _identity_payload(method: MethodAssemblyEvidence) -> dict[str, object]:
    candidate = _selected_candidate(method)
    return {
        "owner": method.owner,
        "method_name": method.method_name,
        "signature": method.signature,
        "definition_signature": method.definition_signature,
        "declaration_die_offset": method.declaration_die_offset,
        "declaration_cu_offset": method.declaration_cu_offset,
        "implementation_die_offset": method.selected_implementation_die_offset,
        "implementation_cu_offset": (
            candidate.implementation_cu_offset if candidate is not None else None
        ),
        "linkage_name": candidate.linkage_name if candidate is not None else None,
        "candidate_count": len(method.candidates),
        "assembly_match_reasons": [item.value for item in method.assembly_match_reasons],
    }


def _source_binding(report: ImplementationDiscoveryReport) -> dict[str, object]:
    return {
        "root_symbol": report.root_symbol,
        "elf_sha256": report.elf_sha256,
        "header_bundle_sha256": report.header_bundle_sha256,
        "header_manifest_sha256": report.header_manifest_sha256,
        "report_schema_version": report.schema_version,
        "artifact_profile": report.artifact_profile.value,
        "analytical_backend": report.analytical_backend,
        "analytical_store_manifest_sha256": report.analytical_store_manifest_sha256,
        "analytical_store_schema_version": report.analytical_store_schema_version,
        "analytical_query_policy": report.analytical_query_policy,
        "disassembly_artifact_key": report.disassembly_artifact_key,
        "disassembly_scope_hash": report.disassembly_scope_hash,
        "target_manifest_hash": _target_manifest_hash(report),
    }


def _range_payload(method: MethodAssemblyEvidence) -> list[dict[str, object]]:
    ranges: list[dict[str, object]] = []
    for candidate in method.candidates:
        for item in candidate.code_ranges:
            ranges.append(
                {
                    "start": item.start_address,
                    "end": item.end_address,
                    "source": item.source,
                    "implementation_die_offset": candidate.implementation_die_offset,
                }
            )
    return ranges


def _instruction_payload(instruction: OrbisInstruction) -> dict[str, object]:
    payload = _jsonable(asdict(instruction))
    if isinstance(payload, dict):
        payload.pop("raw_line", None)
    return payload


def _reference_payload(method: MethodAssemblyEvidence) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    for instruction in method.instructions:
        for reference in instruction.references:
            payload = _jsonable(asdict(reference))
            if isinstance(payload, dict):
                payload["instruction_address"] = instruction.address
                references.append(payload)
    return references


def _control_flow_payload(method: MethodAssemblyEvidence) -> dict[str, object]:
    start = method.selected_function_address
    end = _function_end(method)
    branches: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    external_edges: list[dict[str, object]] = []
    labels = [method.selected_function_name] if method.selected_function_name else []
    for instruction in method.instructions:
        instruction_branches, instruction_calls, instruction_external = _flow_edges(
            instruction, start, end
        )
        branches.extend(instruction_branches)
        calls.extend(instruction_calls)
        external_edges.extend(instruction_external)
    return {
        "status": "inferred" if method.instructions else _NOT_OBSERVED,
        "labels": labels,
        "branches": branches,
        "calls": calls,
        "external_edges": external_edges,
        "summary": {
            "instruction_count": len(method.instructions),
            "branch_count": len(branches),
            "call_count": len(calls),
            "external_edge_count": len(external_edges),
            "entry_address": start,
            "exit_instruction_addresses": [
                item.address
                for item in method.instructions
                if item.mnemonic.lower().startswith(("ret", "jmp"))
            ],
        },
    }


def _flow_edges(
    instruction: OrbisInstruction,
    start: int | None,
    end: int | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    branches: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    external_edges: list[dict[str, object]] = []
    if instruction.mnemonic.lower().startswith("call"):
        call: dict[str, object] = {
            "instruction_address": instruction.address,
            "target_address": instruction.call_target_address,
            "target_name": instruction.call_target_name,
            "indirect": "*" in instruction.operands,
        }
        calls.append(call)
        if _is_external_target(instruction.call_target_address, start, end):
            external_edges.append({"kind": "call", **call})
    for reference in instruction.references:
        if "branch" in reference.kind:
            branch: dict[str, object] = {
                "instruction_address": instruction.address,
                "kind": reference.kind,
                "target_address": reference.address,
                "target_name": reference.resolved_name,
                "resolution_status": reference.resolution_status,
            }
            branches.append(branch)
            if _is_external_target(reference.address, start, end):
                external_edges.append({"kind": "branch", **branch})
        elif reference.kind in {"data", "relocation"}:
            external_edges.append(
                {
                    "kind": reference.kind,
                    "instruction_address": instruction.address,
                    "target_address": reference.address,
                    "target_name": reference.resolved_name,
                    "resolution_status": reference.resolution_status,
                }
            )
    return branches, calls, external_edges


def _is_external_target(address: int | None, start: int | None, end: int | None) -> bool:
    return address is None or start is None or end is None or not start <= address < end


def _relocation_payload(
    method: MethodAssemblyEvidence,
    report: ImplementationDiscoveryReport,
    validation: MethodValidationEvidence | None,
) -> list[object]:
    if validation is not None:
        return [_jsonable(item) for item in validation.context.relocation_ids]
    selected = set(method.relocation_ids)
    if not selected:
        return []
    return [_jsonable(item) for item in report.relocation_entries if item.relocation_id in selected]


def _nid_payload(validation: MethodValidationEvidence | None) -> list[object]:
    if validation is None:
        return []
    return [_jsonable(item) for item in validation.context.nid_ids]


def _validation_payload(validation: MethodValidationEvidence | None) -> dict[str, object]:
    if validation is None:
        return {
            "status": _NOT_OBSERVED,
            "source": "validation-report-not-supplied",
        }
    return {
        "method_id": validation.method_id,
        "relocation_status": validation.relocation_status.value,
        "nid_status": validation.nid_status.value,
        "abi_status": validation.abi.status.value,
        "effects_status": validation.effects.status.value,
        "compiler_status": validation.compiler.status.value,
        "parity_status": validation.parity.status.value,
        "diagnostics": list(validation.diagnostics),
    }


def _dimension_payload(
    validation: MethodValidationEvidence | None, attribute: str
) -> dict[str, object]:
    if validation is None:
        return {"status": _NOT_OBSERVED, "source": "validation-report-not-supplied"}
    value = getattr(validation, attribute)
    return _jsonable(value)


def _abi_payload(
    method: MethodAssemblyEvidence,
    validation: MethodValidationEvidence | None,
) -> dict[str, object]:
    if validation is not None:
        return _jsonable(validation.abi)
    facts = method.dwarf_context.abi_facts if method.dwarf_context is not None else {}
    if not facts:
        return {"status": _NOT_OBSERVED, "source": "doris-context-not-observed"}
    return {"status": "observed", "source": "doris", **_jsonable(facts)}


def _compiler_payload(
    validation: MethodValidationEvidence | None,
    report: ImplementationDiscoveryReport,
    descriptors: tuple[ArtifactDescriptor, ...],
    *,
    assembler: Path | None,
    object_content: bytes | None,
) -> dict[str, object]:
    payload: dict[str, object]
    if validation is not None:
        candidate = _jsonable(validation.compiler)
        payload = dict(candidate) if isinstance(candidate, dict) else {"status": _NOT_OBSERVED}
    else:
        payload = {
            "status": "observed" if _descriptor_for(descriptors, "object") else _NOT_OBSERVED,
            "profile": "orbis-as",
            "diagnostics": (),
        }
    if not isinstance(payload, dict):
        payload = {"status": _NOT_OBSERVED}
    tool = _tool_payload(assembler)
    payload = {**payload, **tool}
    payload["target_triple"] = (
        report.sdk_definition_identity.target_triple
        if report.sdk_definition_identity is not None
        else None
    )
    canonical = _descriptor_for(descriptors, "canonical-assembly")
    object_descriptor = _descriptor_for(descriptors, "object")
    payload["command"] = (
        [str(assembler), "-o", object_descriptor.path, canonical.path]
        if assembler is not None and canonical is not None and object_descriptor is not None
        else []
    )
    payload["source_sha256"] = getattr(canonical, "sha256", None)
    payload["output_sha256"] = getattr(object_descriptor, "sha256", None)
    payload["object_metadata"] = _object_metadata(object_content)
    return payload


def _tool_payload(assembler: Path | None) -> dict[str, object]:
    if assembler is None or not assembler.is_file():
        return {"tool": None, "tool_sha256": None, "version": None, "command_flags": ()}
    return {
        "tool": str(assembler),
        "tool_sha256": _sha256_file(assembler),
        "version": None,
        "command_flags": ("-o",),
    }


def _object_metadata(object_content: bytes | None) -> dict[str, object]:
    if object_content is None:
        return {"status": _NOT_OBSERVED}
    try:
        elf = ELFFile(io.BytesIO(object_content))
        header = elf.header
        sections = tuple(
            section.name
            for section in (elf.get_section(index) for index in range(elf.num_sections()))
            if section is not None
        )
        text = elf.get_section_by_name(".text")
        return {
            "status": "observed",
            "elf_class": str(header["e_ident"]["EI_CLASS"]),
            "machine": str(header["e_machine"]),
            "type": str(header["e_type"]),
            "sections": sections,
            "text_size": text.header["sh_size"] if text is not None else None,
        }
    except ELFError, KeyError, OSError, ValueError:
        return {
            "status": "partial",
            "diagnostics": ("accepted object metadata was not parseable",),
        }


def _descriptor_for(
    descriptors: tuple[ArtifactDescriptor, ...], kind: str
) -> ArtifactDescriptor | None:
    return next((item for item in descriptors if item.kind == kind), None)


def _evidence_status(
    method: MethodAssemblyEvidence,
    descriptors: tuple[ArtifactDescriptor, ...],
    validation: MethodValidationEvidence | None,
) -> dict[str, str]:
    kinds = {item.kind for item in descriptors}
    status = {
        "implementation_identity": method.implementation_status.value,
        "disassembly": method.assembly_status.value,
        "raw_assembly": "observed" if "raw-assembly" in kinds else _NOT_OBSERVED,
        "canonical_assembly": "observed" if "canonical-assembly" in kinds else _NOT_OBSERVED,
        "object": "observed" if "object" in kinds else _NOT_OBSERVED,
        "abi": _NOT_OBSERVED,
        "instruction_safety": _NOT_OBSERVED,
        "compiler": "observed" if "object" in kinds else _NOT_OBSERVED,
        "semantic_parity": _NOT_OBSERVED,
        "live_behavior": _NOT_OBSERVED,
    }
    if validation is not None:
        status.update(
            {
                "abi": validation.abi.status.value,
                "instruction_safety": validation.effects.status.value,
                "compiler": validation.compiler.status.value,
                "semantic_parity": validation.parity.status.value,
            }
        )
    return status


def _transformation_cues(
    method: MethodAssemblyEvidence,
    validation: MethodValidationEvidence | None,
) -> dict[str, object]:
    mnemonics = {item.mnemonic.lower().removesuffix("q") for item in method.instructions}
    effects = validation.effects if validation is not None else None
    object_pointer, hidden_return = _abi_cues(method, validation)
    calls = _call_targets(method)
    return {
        "object_pointer": object_pointer,
        "hidden_return": hidden_return,
        "has_calls": bool(calls),
        "call_targets": list(calls),
        "has_indirect_call": _indirect_call_cue(method, effects),
        "has_conditional_branch": any(
            item.mnemonic.lower().startswith("j") for item in method.instructions
        ),
        "has_return": "ret" in mnemonics,
        "stack": _stack_cue(effects),
        "callee_saved_preserved": effects.callee_saved_preserved if effects is not None else None,
        "status": "observed" if method.instructions else _NOT_OBSERVED,
    }


def _abi_cues(
    method: MethodAssemblyEvidence,
    validation: MethodValidationEvidence | None,
) -> tuple[object, object]:
    if validation is not None:
        return validation.abi.object_pointer, validation.abi.hidden_return
    facts = {} if method.dwarf_context is None else method.dwarf_context.abi_facts
    return facts.get("object_pointer"), facts.get("hidden_return")


def _call_targets(method: MethodAssemblyEvidence) -> tuple[object, ...]:
    return tuple(
        item.call_target_name or item.call_target_address
        for item in method.instructions
        if item.mnemonic.lower().startswith("call")
    )


def _indirect_call_cue(
    method: MethodAssemblyEvidence,
    effects: Any,
) -> bool | None:
    if effects is not None:
        return effects.indirect_call
    return any(
        "*" in item.operands
        for item in method.instructions
        if item.mnemonic.lower().startswith("call")
    )


def _stack_cue(effects: Any) -> dict[str, object]:
    if effects is None:
        return {"status": _NOT_OBSERVED}
    return {
        "status": effects.status.value,
        "delta_min": effects.stack_delta_min,
        "delta_max": effects.stack_delta_max,
        "balanced": effects.stack_balanced,
    }


def _tool_evidence(report: ImplementationDiscoveryReport) -> dict[str, object]:
    return {
        "orbis": _jsonable(report.tool),
        "sdk_definition": _jsonable(report.sdk_definition_identity),
        "invocations": [_jsonable(item) for item in report.tool_invocations],
    }


def _default_context(method: MethodAssemblyEvidence) -> MethodContextPacket:
    candidate = _selected_candidate(method)
    ranges = tuple(
        (item.start_address, item.end_address, item.source)
        for candidate_item in method.candidates
        for item in candidate_item.code_ranges
    )
    diagnostics = method.diagnostics + (
        "Doris validation context was not supplied when the bundle was published",
    )
    return MethodContextPacket(
        declaration_die_offset=method.declaration_die_offset,
        implementation_die_offset=method.selected_implementation_die_offset,
        declaration_cu_offset=method.declaration_cu_offset,
        implementation_cu_offset=(
            candidate.implementation_cu_offset if candidate is not None else None
        ),
        code_ranges=ranges,
        disassembly_addresses=tuple(item.address for item in method.instructions),
        relocation_ids=method.relocation_ids,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )


def _selected_candidate(method: MethodAssemblyEvidence) -> Any | None:
    if method.selected_implementation_die_offset is None:
        return None
    return next(
        (
            item
            for item in method.candidates
            if item.implementation_die_offset == method.selected_implementation_die_offset
        ),
        None,
    )


def _function_end(method: MethodAssemblyEvidence) -> int | None:
    if method.selected_function_address is None or method.selected_function_size is None:
        return None
    return method.selected_function_address + method.selected_function_size


def _target_manifest_hash(report: ImplementationDiscoveryReport) -> str | None:
    payload = [item.to_dict() for item in report.disassembly_target_manifest]
    if not payload:
        return None
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@lru_cache(maxsize=8)
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "CONTEXT_SCHEMA_VERSION",
    "build_context_packet",
    "normalize_raw_assembly",
    "render_context_packet",
]

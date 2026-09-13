"""Project optional validation results into the neutral context contract."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.serialization import to_jsonable
from ...domain.models.implementation_context import ImplementationContextEnrichment
from ...domain.models.implementation_validation import MethodValidationEvidence


def project_method_context(
    evidence: MethodValidationEvidence,
) -> ImplementationContextEnrichment:
    """Convert one validation result without leaking its type into generation."""
    return ImplementationContextEnrichment(
        packet=evidence.context,
        relocation_ids=evidence.context.relocation_ids,
        nid_ids=evidence.context.nid_ids,
        payloads={
            "abi": to_jsonable(evidence.abi),
            "instruction_effects": to_jsonable(evidence.effects),
            "compiler": to_jsonable(evidence.compiler),
            "semantic_parity": to_jsonable(evidence.parity),
            "validation": {
                "method_id": evidence.method_id,
                "relocation_status": evidence.relocation_status.value,
                "nid_status": evidence.nid_status.value,
                "abi_status": evidence.abi.status.value,
                "effects_status": evidence.effects.status.value,
                "compiler_status": evidence.compiler.status.value,
                "parity_status": evidence.parity.status.value,
                "diagnostics": list(evidence.diagnostics),
            },
            "evidence_status": {
                "abi": evidence.abi.status.value,
                "instruction_safety": evidence.effects.status.value,
                "compiler": evidence.compiler.status.value,
                "semantic_parity": evidence.parity.status.value,
            },
            "transformation_cues": {
                "object_pointer": evidence.abi.object_pointer,
                "hidden_return": evidence.abi.hidden_return,
                "has_indirect_call": evidence.effects.indirect_call,
                "stack": {
                    "status": evidence.effects.status.value,
                    "delta_min": evidence.effects.stack_delta_min,
                    "delta_max": evidence.effects.stack_delta_max,
                    "balanced": evidence.effects.stack_balanced,
                },
                "callee_saved_preserved": evidence.effects.callee_saved_preserved,
            },
        },
    )


def project_context_evidence(
    evidence: Mapping[str, MethodValidationEvidence],
) -> dict[str, ImplementationContextEnrichment]:
    """Build the optional method-id projection consumed by artifact publication."""
    return {method_id: project_method_context(item) for method_id, item in evidence.items()}


__all__ = ["project_context_evidence", "project_method_context"]

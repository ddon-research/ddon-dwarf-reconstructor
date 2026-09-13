"""Focused ABI and static-equivalence promotion truth-table tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    CompilerEvidence,
    SemanticParity,
    StaticEquivalenceDisposition,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.domain.services.cpp_reconstruction.abi import classify_return_type
from ddon_dwarf_reconstructor.infrastructure import implementation_method_validation
from ddon_dwarf_reconstructor.infrastructure.implementation_abi_facts import acquire_return_type


class _ContextAttribute:
    def __init__(self, value: object) -> None:
        self.value = value


@pytest.mark.unit
@pytest.mark.functional
def test_return_type_facts_cover_pointer_enum_char_and_hidden_sret_shapes() -> None:
    class ReturnDeclaration:
        def __init__(self, target: object) -> None:
            self.attributes = {"DW_AT_type": _ContextAttribute(0x200)}
            self.target = target

        def get_DIE_from_attribute(self, name: str) -> object | None:  # noqa: N802
            return self.target if name == "DW_AT_type" else None

    pointer = SimpleNamespace(
        offset=0x200,
        tag="DW_TAG_pointer_type",
        attributes={"DW_AT_byte_size": _ContextAttribute(8)},
    )
    pointer_facts = classify_return_type(
        acquire_return_type(object(), ReturnDeclaration(pointer), [])
    )
    assert pointer_facts.return_location == "rax"
    assert pointer_facts.hidden_return is False

    enum_char = SimpleNamespace(
        offset=0x201,
        tag="DW_TAG_enumeration_type",
        attributes={
            "DW_AT_name": _ContextAttribute(b"char"),
            "DW_AT_byte_size": _ContextAttribute(1),
        },
    )
    enum_facts = classify_return_type(
        acquire_return_type(object(), ReturnDeclaration(enum_char), [])
    )
    assert enum_facts.status is ValidationStatus.OBSERVED
    assert enum_facts.kind == "integer"
    assert enum_facts.size == 1

    large = SimpleNamespace(
        offset=0x202,
        tag="DW_TAG_structure_type",
        attributes={"DW_AT_byte_size": _ContextAttribute(24)},
    )
    large_facts = classify_return_type(acquire_return_type(object(), ReturnDeclaration(large), []))
    assert large_facts.return_location == "rax"
    assert large_facts.hidden_return is True

    cyclic = SimpleNamespace(offset=0x203, tag="DW_TAG_typedef", attributes={})
    cyclic.attributes["DW_AT_type"] = _ContextAttribute(0x203)
    cyclic.get_DIE_from_attribute = lambda _name: cyclic
    diagnostics: list[str] = []
    cyclic_facts = classify_return_type(
        acquire_return_type(object(), ReturnDeclaration(cyclic), diagnostics)
    )
    assert cyclic_facts.status is ValidationStatus.FAILED
    assert any("cyclic" in item for item in diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_static_equivalence_disposition_truth_table_is_fail_closed() -> None:
    compiler = CompilerEvidence(
        ValidationStatus.OBSERVED,
        output_path="method.o",
        output_sha256="a" * 64,
        object_metadata={"e_flags": 0x04000000, "section_names": [".text"]},
    )
    complete = SemanticParity(
        ValidationStatus.OBSERVED,
        byte_status=ValidationStatus.OBSERVED,
        cfg_status=ValidationStatus.OBSERVED,
        external_edge_status=ValidationStatus.OBSERVED,
        effect_status=ValidationStatus.OBSERVED,
    )
    promoted = implementation_method_validation._normalize_parity(
        complete,
        ValidationStatus.OBSERVED,
        compiler_evidence=compiler,
        required_dimensions=(("ABI/CFI", ValidationStatus.OBSERVED),),
    )
    assert promoted.static_equivalence is StaticEquivalenceDisposition.TARGET_OBJECT_EQUIVALENT
    assert promoted.to_dict()["static_equivalence"] == "target_object_equivalent"

    not_promoted = implementation_method_validation._normalize_parity(
        complete,
        ValidationStatus.OBSERVED,
        compiler_evidence=compiler,
        required_dimensions=(("ABI/CFI", ValidationStatus.PARTIAL),),
    )
    assert not_promoted.static_equivalence is StaticEquivalenceDisposition.NOT_PROMOTED

    conflicting = implementation_method_validation._normalize_parity(
        SemanticParity(
            ValidationStatus.OBSERVED,
            byte_status=ValidationStatus.OBSERVED,
            cfg_status=ValidationStatus.FAILED,
            external_edge_status=ValidationStatus.OBSERVED,
            effect_status=ValidationStatus.OBSERVED,
        ),
        ValidationStatus.OBSERVED,
        compiler_evidence=compiler,
    )
    assert conflicting.static_equivalence is StaticEquivalenceDisposition.CONFLICTING

    failed = implementation_method_validation._normalize_parity(
        SemanticParity(
            ValidationStatus.OBSERVED,
            byte_status=ValidationStatus.OBSERVED,
            cfg_status=ValidationStatus.OBSERVED,
            external_edge_status=ValidationStatus.OBSERVED,
            effect_status=ValidationStatus.FAILED,
        ),
        ValidationStatus.OBSERVED,
        compiler_evidence=compiler,
    )
    assert failed.static_equivalence is StaticEquivalenceDisposition.FAILED


@pytest.mark.unit
@pytest.mark.functional
def test_abi_completeness_requires_source_facts_and_cfi() -> None:
    facts = {
        "calling_convention": "DW_CC_normal",
        "object_pointer_required": True,
        "object_pointer": "this",
        "formal_parameter_count": 3,
        "located_parameter_count": 3,
        "parameter_locations": ("this:rdi", "value:rsi", "vector:stack+0x20"),
        "hidden_parameters": ("sret",),
        "artificial_parameters": ("this", "sret"),
        "frame_base_locations": ('["rbp"]',),
        "return_type_status": ValidationStatus.OBSERVED,
        "return_type_kind": "aggregate",
        "return_type_size": 24,
        "return_location": "rax",
        "hidden_return": True,
    }
    probe = (CompilerEvidence(ValidationStatus.OBSERVED, profile="abi:aggregate"),)
    assert (
        implementation_method_validation._abi_status(ValidationStatus.OBSERVED, probe, facts)
        is ValidationStatus.OBSERVED
    )

    missing_location = dict(facts, located_parameter_count=2)
    assert (
        implementation_method_validation._abi_status(
            ValidationStatus.OBSERVED, probe, missing_location
        )
        is ValidationStatus.PARTIAL
    )
    missing_return = dict(
        facts, return_type_status=ValidationStatus.NOT_OBSERVED, return_location=None
    )
    assert (
        implementation_method_validation._abi_status(
            ValidationStatus.OBSERVED, probe, missing_return
        )
        is ValidationStatus.PARTIAL
    )
    assert (
        implementation_method_validation._abi_status(ValidationStatus.PARTIAL, probe, facts)
        is ValidationStatus.PARTIAL
    )
    assert (
        implementation_method_validation._abi_status(ValidationStatus.FAILED, probe, facts)
        is ValidationStatus.FAILED
    )

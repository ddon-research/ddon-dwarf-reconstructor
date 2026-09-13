"""Pure return-type policy preserves uncertainty and existing ABI boundary cases."""

import pytest

from ddon_dwarf_reconstructor.domain.models.cpp_reconstruction.abi import ReturnTypeEvidence
from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.domain.services.cpp_reconstruction.abi import classify_return_type

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.mark.parametrize("size", [None, 0, 8, 16, 17, 24])
@pytest.mark.parametrize("tag", ["DW_TAG_structure_type", "DW_TAG_array_type"])
def test_aggregate_return_threshold_preserves_unknown_size(tag: str, size: int | None) -> None:
    facts = classify_return_type(ReturnTypeEvidence(ValidationStatus.OBSERVED, tag, size))
    hidden = size is None or size > 16
    assert facts.kind == "aggregate"
    assert facts.size == size
    assert facts.hidden_return is hidden
    assert facts.return_location == ("rax" if hidden else "rax,rdx")
    assert facts.status is (ValidationStatus.PARTIAL if size is None else ValidationStatus.OBSERVED)


@pytest.mark.parametrize(
    "tag", ["DW_TAG_pointer_type", "DW_TAG_reference_type", "DW_TAG_rvalue_reference_type"]
)
@pytest.mark.parametrize("size", [None, 0, 4, 8])
def test_pointer_return_never_becomes_aggregate(tag: str, size: int | None) -> None:
    facts = classify_return_type(ReturnTypeEvidence(ValidationStatus.OBSERVED, tag, size))
    assert (facts.kind, facts.size, facts.return_location, facts.hidden_return) == (
        "pointer",
        size or 8,
        "rax",
        False,
    )


@pytest.mark.parametrize(
    "name,location", [("FLOAT", "xmm0"), ("long double", "xmm0"), ("char", "rax"), (None, "rax")]
)
def test_scalar_classification_preserves_name_policy(name: str | None, location: str) -> None:
    facts = classify_return_type(
        ReturnTypeEvidence(ValidationStatus.OBSERVED, "DW_TAG_enumeration_type", 4, name)
    )
    assert facts.return_location == location
    assert facts.status is ValidationStatus.OBSERVED


@pytest.mark.parametrize(
    "status", [ValidationStatus.NOT_OBSERVED, ValidationStatus.PARTIAL, ValidationStatus.FAILED]
)
def test_unresolved_evidence_cannot_be_promoted(status: ValidationStatus) -> None:
    facts = classify_return_type(ReturnTypeEvidence(status))
    assert (facts.status, facts.kind, facts.return_location) == (status, "unknown", None)


def test_void_and_unsupported_types_have_distinct_dispositions() -> None:
    void = classify_return_type(ReturnTypeEvidence(ValidationStatus.OBSERVED, is_void=True))
    assert (void.kind, void.size, void.return_location) == ("void", 0, "void")
    unknown = classify_return_type(ReturnTypeEvidence(ValidationStatus.OBSERVED, "", 12))
    assert unknown.status is ValidationStatus.PARTIAL
    assert unknown.size == 12
    assert unknown.diagnostics == ("unsupported return type DIE tag: unknown",)

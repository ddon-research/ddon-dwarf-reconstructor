"""Pure classification of acquired return-type facts using the existing PS4 ABI policy."""

from __future__ import annotations

from ...models.cpp_reconstruction.abi import SCALAR_TYPE_TAGS, ReturnTypeEvidence, ReturnTypeFacts
from ...models.implementation_validation import ValidationStatus

_POINTER_TAGS = frozenset(
    {"DW_TAG_pointer_type", "DW_TAG_reference_type", "DW_TAG_rvalue_reference_type"}
)
_AGGREGATE_TAGS = frozenset(
    {"DW_TAG_structure_type", "DW_TAG_class_type", "DW_TAG_union_type", "DW_TAG_array_type"}
)


def classify_return_type(evidence: ReturnTypeEvidence) -> ReturnTypeFacts:
    """Preserve the current classification rules without acquiring additional evidence."""
    if evidence.status is not ValidationStatus.OBSERVED:
        return ReturnTypeFacts(evidence.status, "unknown", evidence.size, None, None)
    if evidence.is_void:
        return ReturnTypeFacts(ValidationStatus.OBSERVED, "void", 0, "void", False)
    if evidence.tag in _POINTER_TAGS:
        return ReturnTypeFacts(
            ValidationStatus.OBSERVED, "pointer", evidence.size or 8, "rax", False
        )
    if evidence.tag in SCALAR_TYPE_TAGS:
        return _scalar_return(evidence)
    if evidence.tag in _AGGREGATE_TAGS:
        return _aggregate_return(evidence.size)
    return ReturnTypeFacts(
        ValidationStatus.PARTIAL,
        "unknown",
        evidence.size,
        None,
        None,
        (f"unsupported return type DIE tag: {evidence.tag or 'unknown'}",),
    )


def _scalar_return(evidence: ReturnTypeEvidence) -> ReturnTypeFacts:
    floating = any(item in (evidence.name or "").casefold() for item in ("float", "double"))
    return ReturnTypeFacts(
        ValidationStatus.OBSERVED,
        "float" if floating else "integer",
        evidence.size,
        "xmm0" if floating else "rax",
        False,
    )


def _aggregate_return(size: int | None) -> ReturnTypeFacts:
    hidden = size is None or size > 16
    status = ValidationStatus.OBSERVED if size is not None else ValidationStatus.PARTIAL
    return ReturnTypeFacts(status, "aggregate", size, "rax" if hidden else "rax,rdx", hidden)

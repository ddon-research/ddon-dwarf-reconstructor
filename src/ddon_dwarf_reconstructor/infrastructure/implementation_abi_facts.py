"""Bounded DWARF return-type facts for the PS4 ABI contract."""

from __future__ import annotations

from typing import Any

from ..domain.models.cpp_reconstruction.abi import SCALAR_TYPE_TAGS, ReturnTypeEvidence
from ..domain.models.implementation_validation import ValidationStatus

_QUALIFIER_TAGS = frozenset(
    {
        "DW_TAG_typedef",
        "DW_TAG_const_type",
        "DW_TAG_volatile_type",
        "DW_TAG_restrict_type",
        "DW_TAG_atomic_type",
    }
)


def acquire_return_type(
    store: Any, declaration_die: Any, diagnostics: list[str]
) -> ReturnTypeEvidence:
    """Resolve a declaration return type within a bounded DIE chain."""
    attributes = getattr(declaration_die, "attributes", {})
    type_attribute = attributes.get("DW_AT_type") if isinstance(attributes, dict) else None
    if type_attribute is None:
        return ReturnTypeEvidence(ValidationStatus.OBSERVED, is_void=True)
    current = _referenced_die(store, declaration_die, type_attribute, diagnostics)
    if current is None:
        return ReturnTypeEvidence(ValidationStatus.NOT_OBSERVED)
    seen: set[int] = set()
    for _ in range(16):
        offset = getattr(current, "offset", None)
        if isinstance(offset, int):
            if offset in seen:
                diagnostics.append("return type DIE chain is cyclic")
                return ReturnTypeEvidence(ValidationStatus.FAILED)
            seen.add(offset)
        tag = str(getattr(current, "tag", ""))
        if tag in _QUALIFIER_TAGS:
            current = _next_type_die(store, current, diagnostics)
            if current is None:
                return ReturnTypeEvidence(ValidationStatus.NOT_OBSERVED)
            continue
        return _terminal_return_evidence(current, tag)
    diagnostics.append("return type DIE chain exceeded the bounded depth")
    return ReturnTypeEvidence(ValidationStatus.PARTIAL)


def _terminal_return_evidence(die: Any, tag: str) -> ReturnTypeEvidence:
    attributes = getattr(die, "attributes", {})
    return ReturnTypeEvidence(
        ValidationStatus.OBSERVED,
        tag=tag,
        size=_attribute_int(attributes, "DW_AT_byte_size"),
        name=_attribute_text(attributes, "DW_AT_name") if tag in SCALAR_TYPE_TAGS else None,
    )


def _next_type_die(store: Any, owner: Any, diagnostics: list[str]) -> Any | None:
    attributes = getattr(owner, "attributes", {})
    return _referenced_die_from_attributes(store, owner, attributes, diagnostics)


def _referenced_die(store: Any, owner: Any, attribute: Any, diagnostics: list[str]) -> Any | None:
    getter = getattr(owner, "get_DIE_from_attribute", None)
    if callable(getter):
        resolved = getter("DW_AT_type")
        if resolved is not None:
            return resolved
    value = getattr(attribute, "value", None)
    if not isinstance(value, int):
        diagnostics.append("return type reference is not an integer DIE offset")
        return None
    form = str(getattr(attribute, "form", ""))
    cu = getattr(owner, "cu", None)
    cu_offset = getattr(cu, "cu_offset", 0)
    absolute = value if form == "DW_FORM_ref_addr" else value + cu_offset
    result = store.get_die(absolute)
    if getattr(result, "items", ()):
        return result.items[0]
    diagnostics.append(f"return type DIE 0x{absolute:x} was not found")
    return None


def _referenced_die_from_attributes(
    store: Any, owner: Any, attributes: Any, diagnostics: list[str]
) -> Any | None:
    attribute = attributes.get("DW_AT_type") if isinstance(attributes, dict) else None
    if attribute is None:
        diagnostics.append("return type chain ended without DW_AT_type")
        return None
    return _referenced_die(store, owner, attribute, diagnostics)


def _attribute_int(attributes: Any, name: str) -> int | None:
    if not isinstance(attributes, dict):
        return None
    value = getattr(attributes.get(name), "value", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _attribute_text(attributes: Any, name: str) -> str | None:
    if not isinstance(attributes, dict):
        return None
    value = getattr(attributes.get(name), "value", None)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else None


__all__ = ["acquire_return_type"]

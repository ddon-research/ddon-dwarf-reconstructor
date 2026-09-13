"""Decode DWARF reference attributes without a second store lookup."""

from __future__ import annotations

from typing import Any

from ...domain.models.analytical_dwarf import QueryStatus

_RELATIVE_REFERENCE_FORMS = frozenset(
    {
        "DW_FORM_ref1",
        "DW_FORM_ref2",
        "DW_FORM_ref4",
        "DW_FORM_ref8",
        "DW_FORM_ref",
        "DW_FORM_ref_udata",
    }
)


def reference_target_for_attribute(
    attribute: Any,
    *,
    unit_offset: int | None,
    default_unit_offset: int = 0,
) -> tuple[int | None, QueryStatus]:
    """Decode one hydrated reference attribute using producer semantics."""
    if attribute is None:
        return None, QueryStatus.NOT_FOUND
    raw = _integer_or_none(getattr(attribute, "raw_value", None))
    if raw is None:
        raw = _integer_or_none(getattr(attribute, "value", None))
    if raw is None:
        return None, QueryStatus.PARTIAL

    form = str(getattr(attribute, "form", ""))
    if form in _RELATIVE_REFERENCE_FORMS:
        base = unit_offset if unit_offset is not None else default_unit_offset
        return base + raw, QueryStatus.COMPLETE
    if form == "DW_FORM_ref_addr":
        return raw, QueryStatus.COMPLETE
    return None, QueryStatus.PARTIAL


def _integer_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

"""Typed acquired return-type evidence and conservative ABI classifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..implementation_validation import ValidationStatus

SCALAR_TYPE_TAGS = frozenset({"DW_TAG_base_type", "DW_TAG_enumeration_type"})


@dataclass(frozen=True, slots=True)
class ReturnTypeEvidence:
    """Terminal DWARF facts without live DIE, store, or compilation-unit references."""

    status: ValidationStatus
    tag: str = ""
    size: int | None = None
    name: str | None = None
    is_void: bool = False


@dataclass(frozen=True, slots=True)
class ReturnTypeFacts:
    """Existing ABI disposition, including uncertainty and classification diagnostics."""

    status: ValidationStatus
    kind: Literal["void", "pointer", "float", "integer", "aggregate", "unknown"]
    size: int | None
    return_location: str | None
    hidden_return: bool | None
    diagnostics: tuple[str, ...] = ()

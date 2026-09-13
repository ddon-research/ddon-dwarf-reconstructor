"""Neutral source-bound context attached to discovered implementation methods.

This contract belongs to implementation discovery, not to the optional
implementation-validation feature.  Keeping it here lets generation retain
DWARF/CFI/location context even when validation is not installed or requested.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

from ...core.serialization import to_jsonable


@dataclass(frozen=True, slots=True)
class MethodContextPacket:
    """One bounded join of DWARF, machine-code, and diagnostic context."""

    declaration_die_offset: int | None
    implementation_die_offset: int | None
    declaration_cu_offset: int | None
    implementation_cu_offset: int | None
    code_ranges: tuple[tuple[int, int, str], ...] = ()
    locations: tuple[dict[str, object], ...] = ()
    cfi: tuple[dict[str, object], ...] = ()
    disassembly_addresses: tuple[int, ...] = ()
    relocation_ids: tuple[str, ...] = ()
    nid_ids: tuple[str, ...] = ()
    abi_facts: dict[str, object] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return to_jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class ImplementationContextEnrichment:
    """Optional evidence overlay supplied by an external analysis feature."""

    packet: MethodContextPacket | None = None
    relocation_ids: tuple[object, ...] = ()
    nid_ids: tuple[object, ...] = ()
    payloads: Mapping[str, object] = field(default_factory=dict)


__all__ = ["ImplementationContextEnrichment", "MethodContextPacket"]

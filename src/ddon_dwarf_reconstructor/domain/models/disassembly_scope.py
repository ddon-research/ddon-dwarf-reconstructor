"""Source-bound disassembly scope contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

_MAX_ADDRESS = 1 << 64


@dataclass(frozen=True, slots=True)
class DisassemblyTarget:
    """One DWARF-derived method target requested from the disassembler."""

    target_id: str
    declaration_die_offset: int | None
    implementation_die_offset: int | None
    declaration_cu_offset: int | None
    implementation_cu_offset: int | None
    ranges: tuple[tuple[int, int], ...]
    range_provenance: tuple[str, ...] = ()
    qualified_name: str | None = None
    linkage_name: str | None = None
    signature: str | None = None

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("DisassemblyTarget requires a stable target_id")
        for start, end in self.ranges:
            if not 0 <= start < end < _MAX_ADDRESS:
                raise ValueError("DisassemblyTarget ranges must fit the 64-bit address domain")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DisassemblyRequest:
    """Deterministic scope for one bounded Orbis disassembly artifact."""

    root_symbol: str
    source_identity: str | None
    targets: tuple[DisassemblyTarget, ...] = ()
    selection_policy: str = "dwarf-range-closure-v1"

    @classmethod
    def root_only(cls, root_symbol: str) -> DisassemblyRequest:
        """Build the compatibility request used by knowledge-export callers."""
        return cls(root_symbol, None, (), "root-prefix-v1")

    @property
    def scope_hash(self) -> str:
        payload = {
            "root_symbol": self.root_symbol,
            "source_identity": self.source_identity,
            "selection_policy": self.selection_policy,
            "targets": [target.to_dict() for target in self.targets],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "root_symbol": self.root_symbol,
            "source_identity": self.source_identity,
            "selection_policy": self.selection_policy,
            "scope_hash": self.scope_hash,
            "targets": [target.to_dict() for target in self.targets],
        }


__all__ = ["DisassemblyRequest", "DisassemblyTarget"]

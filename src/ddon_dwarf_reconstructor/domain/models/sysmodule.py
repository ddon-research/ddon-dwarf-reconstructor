"""Typed Sysmodule loader identifiers from the local Orbis documentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SysmoduleId:
    """One ``sceSysmoduleLoadModule``/UnloadModule identifier."""

    name: str
    value: int
    source: str
    sdk_version: str

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-compatible identifier."""
        return asdict(self)


__all__ = ["SysmoduleId"]

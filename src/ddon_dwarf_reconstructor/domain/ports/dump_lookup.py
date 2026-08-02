"""Application-facing contract for compressed-DWARF definition lookup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol


class DumpDefinitionLocation(Protocol):
    """Minimum indexed location evidence needed by class discovery."""

    cu_offset: str
    die_offset: str
    completeness_score: int


class DumpLookupPort(Protocol):
    """Narrow port implemented by the infrastructure dump sidecar adapter."""

    def find_class_definitions(self, class_name: str) -> Sequence[DumpDefinitionLocation]: ...

    def find_method_implementation(self, declaration_offset: int) -> int | None: ...


DumpLookupFactory = Callable[[Path, Path | None], DumpLookupPort]

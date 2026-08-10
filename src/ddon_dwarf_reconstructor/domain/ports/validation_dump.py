"""Explicit validation-only contract for compressed-DWARF dump evidence."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol


class DumpDefinitionLocation(Protocol):
    """Minimum indexed location evidence needed by validation discovery."""

    cu_offset: str
    die_offset: str
    completeness_score: int


class ValidationDumpPort(Protocol):
    """Compressed-dump lookup retained only for explicit validation runs."""

    def find_class_definitions(self, class_name: str) -> Sequence[DumpDefinitionLocation]: ...

    def find_method_implementation(self, declaration_offset: int) -> int | None: ...


ValidationDumpFactory = Callable[[Path, Path | None], ValidationDumpPort]

"""Narrow parsing port used by application orchestration."""

from __future__ import annotations

from typing import Protocol

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ..models.dwarf import ClassInfo
from .type_resolution import TypeNameResolver


class ClassParserPort(Protocol):
    """Operations required by generation orchestration."""

    timed_out_symbols: set[str]
    type_resolver: TypeNameResolver

    def find_class(
        self, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def parse_class_info(self, cu: DwarfCompilationUnit, class_die: DwarfEntry) -> ClassInfo: ...

    def _find_die_and_cu_by_offset(
        self, offset: int
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

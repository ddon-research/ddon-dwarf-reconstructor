"""State model for one bounded class-discovery scan."""

from __future__ import annotations

from dataclasses import dataclass

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE


@dataclass
class ScanState:
    """Mutable aggregate accumulated during one full-DWARF scan."""

    fallback_candidate: tuple[CompileUnit, DIE] | None = None
    best_candidate: DIE | None = None
    best_cu: CompileUnit | None = None
    best_score: int = -1
    timed_out: bool = False
    candidates_found: int = 0
    non_improving_complete_candidates: int = 0
    stop_after_non_improving: bool = False
    early_result: tuple[CompileUnit, DIE] | None = None

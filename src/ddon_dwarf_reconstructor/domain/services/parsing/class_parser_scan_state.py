"""State model for one bounded class-discovery scan."""

from __future__ import annotations

from dataclasses import dataclass

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry


@dataclass
class ScanState:
    """Mutable aggregate accumulated during one full-DWARF scan."""

    fallback_candidate: tuple[DwarfCompilationUnit, DwarfEntry] | None = None
    best_candidate: DwarfEntry | None = None
    best_cu: DwarfCompilationUnit | None = None
    best_score: int = -1
    timed_out: bool = False
    candidates_found: int = 0
    non_improving_complete_candidates: int = 0
    stop_after_non_improving: bool = False
    early_result: tuple[DwarfCompilationUnit, DwarfEntry] | None = None

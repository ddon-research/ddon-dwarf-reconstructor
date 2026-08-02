"""Typed outcomes for bounded DWARF symbol searches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .definition_selection import DefinitionCandidate


class SearchStatus(StrEnum):
    """Evidence state produced by a bounded search."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Candidate, status, and diagnostics from one targeted search."""

    status: SearchStatus
    candidate: DefinitionCandidate | None
    elapsed_seconds: float
    cus_searched: int
    diagnostics: tuple[str, ...] = ()

    @property
    def die_offset(self) -> int | None:
        """Return the candidate offset without discarding the evidence status."""
        return self.candidate.die_offset if self.candidate is not None else None

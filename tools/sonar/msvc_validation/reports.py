"""Typed summary helpers for per-header compiler evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationCounts:
    """Counts that distinguish incomplete compiler evidence from failures."""

    passed: int = 0
    failed: int = 0
    timed_out: int = 0
    not_observed: int = 0

    @property
    def complete(self) -> bool:
        return self.failed == 0 and self.timed_out == 0 and self.not_observed == 0

    def to_dict(self) -> dict[str, int]:
        return {
            "failed": self.failed,
            "not_observed": self.not_observed,
            "passed": self.passed,
            "timed_out": self.timed_out,
        }


def validation_counts(results: Iterable[Mapping[str, object]]) -> ValidationCounts:
    """Count per-header outcomes without treating missing markers as passes."""
    counts = {"passed": 0, "failed": 0, "timed_out": 0, "not_observed": 0}
    for result in results:
        status = str(result.get("status", "not_observed"))
        if status not in counts:
            status = "not_observed"
        counts[status] += 1
    return ValidationCounts(**counts)

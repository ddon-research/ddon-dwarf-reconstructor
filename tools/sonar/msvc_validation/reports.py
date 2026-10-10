"""Typed summary helpers for per-header compiler evidence."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

DIAGNOSTIC_LINE = re.compile(
    r"^([A-Za-z0-9_./\\:-]+)\((\d+)\):\s+(?:fatal\s+)?error\s+([CE]\d{4}):",
    re.IGNORECASE | re.MULTILINE,
)


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


def aggregate_unit_metrics(
    results: list[dict[str, object]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int], int]:
    """Summarize diagnostic classes without mistaking repeated lines for unique sites."""
    failure_classes: dict[str, int] = {}
    diagnostic_codes: dict[str, int] = {}
    raw_counts: dict[str, int] = {}
    unique_locations: dict[str, set[tuple[str, str]]] = {}
    error_limit_unit_count = 0
    for result in results:
        failure_class = str(result["failure_class"])
        failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
        codes = result["diagnostic_codes"]
        if not isinstance(codes, list):
            continue
        for code in codes:
            diagnostic_codes[str(code)] = diagnostic_codes.get(str(code), 0) + 1
        if "C1003" in codes:
            error_limit_unit_count += 1
        for key in ("stdout_log", "stderr_log"):
            path = Path(str(result[key]))
            content = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            for match in DIAGNOSTIC_LINE.finditer(content):
                code = match.group(3).upper()
                raw_counts[code] = raw_counts.get(code, 0) + 1
                unique_locations.setdefault(code, set()).add(
                    (Path(match.group(1)).name, match.group(2))
                )
    unique_location_counts = {key: len(value) for key, value in sorted(unique_locations.items())}
    return (
        failure_classes,
        diagnostic_codes,
        raw_counts,
        unique_location_counts,
        error_limit_unit_count,
    )

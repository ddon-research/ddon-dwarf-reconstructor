"""Enforce total and high-risk coverage thresholds from coverage.py JSON."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

GROUPS = {
    "parsing": ("/domain/services/parsing/",),
    "generation": ("/domain/services/generation/", "/application/generators/"),
    "orchestration": (
        "/application/exporters/",
        "/application/generators/",
        "/main.py",
        "/artifact_cli.py",
    ),
    "artifact": (
        "/infrastructure/artifacts.py",
        "/infrastructure/orbis_objdump.py",
        "/infrastructure/zstd_dump",
    ),
}
TOTAL_LINE_THRESHOLD = 80.0
GROUP_LINE_THRESHOLD = 80.0
GROUP_BRANCH_THRESHOLD = 70.0


@dataclass(frozen=True, slots=True)
class CoverageSummary:
    statements: int
    missing_lines: int
    branches: int
    missing_branches: int

    @property
    def line_percent(self) -> float:
        return _percent(self.statements - self.missing_lines, self.statements)

    @property
    def branch_percent(self) -> float:
        return _percent(self.branches - self.missing_branches, self.branches)

    def add(self, other: CoverageSummary) -> CoverageSummary:
        return CoverageSummary(
            self.statements + other.statements,
            self.missing_lines + other.missing_lines,
            self.branches + other.branches,
            self.missing_branches + other.missing_branches,
        )


def _percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered * 100.0 / total


def _summary(value: object) -> CoverageSummary:
    data = cast(dict[str, object], value)
    return CoverageSummary(
        statements=int(data["num_statements"]),
        missing_lines=int(data["missing_lines"]),
        branches=int(data["num_branches"]),
        missing_branches=int(data["missing_branches"]),
    )


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    return any(prefix in normalized for prefix in prefixes)


def read_report(path: Path) -> dict[str, CoverageSummary]:
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    files = cast(dict[str, object], payload["files"])
    summaries = {
        path_text: _summary(cast(dict[str, object], value)["summary"])
        for path_text, value in files.items()
    }
    result = {"total": _summary(cast(dict[str, object], payload["totals"]))}
    for name, prefixes in GROUPS.items():
        group = CoverageSummary(0, 0, 0, 0)
        for path_text, summary in summaries.items():
            if _matches(path_text, prefixes):
                group = group.add(summary)
        result[name] = group
    return result


def violations(report: dict[str, CoverageSummary]) -> list[str]:
    failures: list[str] = []
    total = report["total"]
    if total.line_percent < TOTAL_LINE_THRESHOLD:
        failures.append(
            f"total line coverage {total.line_percent:.1f}% is below {TOTAL_LINE_THRESHOLD:.1f}%"
        )
    for name in GROUPS:
        summary = report[name]
        if summary.line_percent < GROUP_LINE_THRESHOLD:
            failures.append(
                f"{name} line coverage {summary.line_percent:.1f}% is below "
                f"{GROUP_LINE_THRESHOLD:.1f}%"
            )
        if summary.branch_percent < GROUP_BRANCH_THRESHOLD:
            failures.append(
                f"{name} branch coverage {summary.branch_percent:.1f}% is below "
                f"{GROUP_BRANCH_THRESHOLD:.1f}%"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, nargs="?", default=Path("coverage.json"))
    args = parser.parse_args(argv)
    report = read_report(args.report)
    for name, summary in report.items():
        print(f"{name}: lines={summary.line_percent:.1f}% branches={summary.branch_percent:.1f}%")
    failures = violations(report)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

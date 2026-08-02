from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.quality.check_coverage import read_report, violations

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _summary(statements: int, missing: int, branches: int, missing_branches: int) -> dict[str, int]:
    return {
        "num_statements": statements,
        "missing_lines": missing,
        "num_branches": branches,
        "missing_branches": missing_branches,
    }


@pytest.mark.unit
def test_coverage_checker_aggregates_named_high_risk_groups(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(
            {
                "totals": _summary(100, 10, 100, 20),
                "files": {
                    "src\\ddon_dwarf_reconstructor\\domain\\services\\parsing\\parser.py": {
                        "summary": _summary(50, 2, 20, 2)
                    },
                    "src/ddon_dwarf_reconstructor/infrastructure/artifacts.py": {
                        "summary": _summary(50, 3, 20, 3)
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = read_report(report_path)

    assert report["parsing"].line_percent == pytest.approx(96.0)
    assert report["artifact"].branch_percent == pytest.approx(85.0)
    assert violations(report) == []


@pytest.mark.unit
def test_coverage_checker_reports_line_and_branch_threshold_failures(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(
            {
                "totals": _summary(100, 30, 100, 40),
                "files": {
                    "src/ddon_dwarf_reconstructor/domain/services/parsing/parser.py": {
                        "summary": _summary(10, 3, 10, 4)
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    failures = violations(read_report(report_path))

    assert "total line coverage 70.0% is below 80.0%" in failures
    assert "parsing line coverage 70.0% is below 80.0%" in failures
    assert "parsing branch coverage 60.0% is below 70.0%" in failures

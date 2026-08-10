"""Process isolation, sampling, timeout, and atomic manifest behavior."""

import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState, PerformanceWorkload
from ddon_dwarf_reconstructor.infrastructure.performance.runner import PerformanceRunner
from ddon_dwarf_reconstructor.infrastructure.performance.workloads import build_fixture_workload

pytestmark = [pytest.mark.unit, pytest.mark.non_functional]


def test_runner_publishes_bounded_metrics_and_manifest(tmp_path: Path) -> None:
    """The runner captures process resources without modifying the target workload."""
    workload = build_fixture_workload(
        repository_root=Path.cwd(),
        name="fixture",
        state=ColdWarmState.WARM,
        timeout_seconds=10,
    )

    summary = PerformanceRunner(tmp_path / "artifacts", sample_interval_seconds=0.02).run(workload)

    assert summary.status.value == "observed"
    assert summary.return_code == 0
    assert summary.manifest_path is not None and summary.manifest_path.exists()
    values = {metric.name: metric.value for metric in summary.metrics}
    assert values["wall_time_seconds"] is not None
    assert values["peak_rss_bytes"] is not None
    assert values["sample_count"] >= 1
    assert all(path is None or path.exists() for path in (summary.stdout_path, summary.stderr_path))


def test_runner_marks_timeout_as_partial_and_terminates_child(tmp_path: Path) -> None:
    """A bounded timeout publishes partial evidence and returns control to the caller."""
    workload = PerformanceWorkload(
        "timeout",
        (sys.executable, "-c", "import time; time.sleep(3)"),
        Path.cwd(),
        ColdWarmState.COLD,
        timeout_seconds=0.1,
    )

    summary = PerformanceRunner(tmp_path / "artifacts", sample_interval_seconds=0.02).run(workload)

    assert summary.status.value == "partial"
    assert summary.diagnostics
    assert summary.return_code is not None

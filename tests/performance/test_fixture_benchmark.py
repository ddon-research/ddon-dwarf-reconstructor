"""Deterministic resource budget for the reusable performance runner."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState
from ddon_dwarf_reconstructor.infrastructure.performance.runner import PerformanceRunner
from ddon_dwarf_reconstructor.infrastructure.performance.workloads import build_fixture_workload

pytestmark = [
    pytest.mark.integration,
    pytest.mark.non_functional,
    pytest.mark.performance,
]


def test_deterministic_fixture_has_bounded_wall_time_and_resource_evidence(
    tmp_path: Path,
) -> None:
    """The explicit fixture tier can gate a stable budget without real PS4 inputs."""
    workload = build_fixture_workload(
        repository_root=Path.cwd(),
        name="fixture-budget",
        state=ColdWarmState.WARM,
        timeout_seconds=10,
    )

    summary = PerformanceRunner(tmp_path / "artifacts", sample_interval_seconds=0.02).run(workload)
    metrics = {metric.name: metric.value for metric in summary.metrics}

    assert summary.return_code == 0
    assert metrics["wall_time_seconds"] is not None
    assert metrics["wall_time_seconds"] < 5.0
    assert metrics["peak_rss_bytes"] is not None
    assert metrics["sample_count"] is not None and metrics["sample_count"] >= 1

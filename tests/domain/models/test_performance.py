"""Contracts for source-bound performance evidence."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import (
    ColdWarmState,
    EvidenceStatus,
    MetricRecord,
    PerformanceWorkload,
    RuntimeDescriptor,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_workload_fingerprint_is_stable_and_includes_state(tmp_path: Path) -> None:
    """Like-for-like comparisons can rely on the typed workload fingerprint."""
    first = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.WARM,
        configuration=(("version", "1"),),
    )
    second = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.WARM,
        configuration=(("version", "1"),),
    )
    cold = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.COLD,
        configuration=(("version", "1"),),
    )

    assert first.configuration_fingerprint == second.configuration_fingerprint
    assert first.configuration_fingerprint != cold.configuration_fingerprint


def test_metric_keeps_unavailable_evidence_explicit() -> None:
    """Missing counters remain status-bearing records rather than zero values."""
    metric = MetricRecord("read_bytes", None, "bytes", EvidenceStatus.UNAVAILABLE, "counter denied")

    assert metric.to_dict() == {
        "name": "read_bytes",
        "value": None,
        "unit": "bytes",
        "status": "unavailable",
        "detail": "counter denied",
    }


def test_runtime_descriptor_participates_in_workload_identity(tmp_path: Path) -> None:
    """GIL and compiled-runtime variants cannot be mixed in one baseline."""
    gil = RuntimeDescriptor("cpython-3.14.6", "CPython", "3.14.6", True)
    free = RuntimeDescriptor("cpython-3.14.6-free-threaded", "CPython", "3.14.6", False)
    first = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.WARM,
        runtime=gil,
    )
    second = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.WARM,
        runtime=free,
    )

    assert first.configuration_fingerprint != second.configuration_fingerprint

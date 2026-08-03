"""SQLite schema, typed values, comparisons, and deterministic exports."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import (
    ColdWarmState,
    EvidenceStatus,
    MethodSummary,
    MetricRecord,
    PerformanceWorkload,
    ProfileArtifact,
    RunSummary,
    RuntimeDescriptor,
)
from ddon_dwarf_reconstructor.infrastructure.performance.export import export_history
from ddon_dwarf_reconstructor.infrastructure.performance.history import HistoryStore

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_history_round_trips_typed_metrics_and_method_summaries(tmp_path: Path) -> None:
    """SQLite retains typed aggregate values and normalized method rows."""
    store = HistoryStore(tmp_path / "benchmarks.sqlite3")
    first = _summary(tmp_path, "run-1", 1.0)
    second = _summary(tmp_path, "run-2", 2.0)
    store.record(first)
    store.record(second)

    rows = store.rows("fixture")
    comparison = store.compare(workload="fixture")

    assert store.integrity_check() == "ok"
    assert len(rows) == 2
    assert rows[-1].metrics["wall_time_seconds"]["value"] == 2.0
    assert rows[-1].method_metrics[0]["name"] == "fixture_method"
    assert rows[-1].runtime_name == "cpython-3.14.6"
    assert rows[-1].gil_enabled is True
    assert comparison["status"] == "observed"
    assert comparison["deltas"]["wall_time_seconds"] == 1.0


def test_history_exports_are_repeatable_and_static_site_safe(tmp_path: Path) -> None:
    """Repeated exports are byte-identical and contain explicit empty-state support."""
    store = HistoryStore(tmp_path / "benchmarks.sqlite3")
    store.record(_summary(tmp_path, "run-1", 1.0))
    output_dir = tmp_path / "resources" / "performance"
    markdown = tmp_path / "docs" / "benchmark-history.md"

    export_history(store, output_dir, markdown_path=markdown)
    first_json = (output_dir / "benchmark-history.json").read_bytes()
    first_csv = (output_dir / "benchmark-history.csv").read_bytes()
    first_markdown = markdown.read_bytes()
    export_history(store, output_dir, markdown_path=markdown)

    assert first_json == (output_dir / "benchmark-history.json").read_bytes()
    assert first_csv == (output_dir / "benchmark-history.csv").read_bytes()
    assert first_markdown == markdown.read_bytes()
    assert b"Latest like-for-like baselines" in first_markdown
    assert b"Latest like-for-like deltas" in first_markdown


def _summary(tmp_path: Path, run_id: str, wall_seconds: float) -> RunSummary:
    workload = PerformanceWorkload(
        "fixture",
        ("python", "-m", "fixture"),
        tmp_path,
        ColdWarmState.WARM,
        configuration=(("fixture", "v1"),),
        runtime=RuntimeDescriptor("cpython-3.14.6", "CPython", "3.14.6", True),
    )
    return RunSummary(
        run_id=run_id,
        workload=workload,
        status=EvidenceStatus.OBSERVED,
        started_at=f"2026-08-03T00:00:0{run_id[-1]}+00:00",
        duration_seconds=wall_seconds,
        return_code=0,
        git_revision="abc",
        git_dirty=False,
        python_version="3.14.6",
        platform_name="test",
        machine_profile="test-machine",
        source_identity="source-sha",
        runtime_name="cpython-3.14.6",
        runtime_implementation="CPython",
        gil_enabled=True,
        profiler_mode="cprofile",
        metrics=(
            MetricRecord("wall_time_seconds", wall_seconds, "seconds", EvidenceStatus.OBSERVED),
            MetricRecord("peak_rss_bytes", 1024, "bytes", EvidenceStatus.OBSERVED),
        ),
        method_summaries=(MethodSummary("cprofile", "fixture_method", rank=1, call_count=2),),
        artifacts=(
            ProfileArtifact(
                "cprofile",
                "pstats",
                None,
                None,
                None,
                EvidenceStatus.NOT_OBSERVED,
                detail="test summary",
            ),
        ),
    )

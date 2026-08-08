"""Tests for explicit pre-store benchmark baselines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark import (
    _baseline_measurements,
    _baseline_summary_status,
    _runtime_comparison,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_baselines_remain_unobserved_without_explicit_inputs(tmp_path: Path) -> None:
    baselines = _baseline_measurements(
        tmp_path / "source.elf",
        tmp_path / "benchmark",
        ("Thing",),
        1,
        run_current_baseline=False,
    )

    assert _baseline_summary_status(baselines) == "not_observed"
    assert baselines["current_runtime"]["status"] == "not_observed"


def test_explicit_baseline_failures_are_blocked_not_silent(tmp_path: Path) -> None:
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.current_runtime_baseline",
            side_effect=RuntimeError("live baseline unavailable"),
        ),
    ):
        baselines = _baseline_measurements(
            tmp_path / "source.elf",
            tmp_path / "benchmark",
            ("Thing",),
            1,
            run_current_baseline=True,
        )

    assert _baseline_summary_status(baselines) == "blocked"
    assert baselines["current_runtime"]["status"] == "blocked"


def test_explicit_live_baseline_is_observed(tmp_path: Path) -> None:
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.current_runtime_baseline",
        return_value={"status": "observed", "queries": []},
    ):
        baselines = _baseline_measurements(
            tmp_path / "source.elf",
            tmp_path / "benchmark",
            ("rLayout",),
            1,
            run_current_baseline=True,
        )

    assert _baseline_summary_status(baselines) == "observed"


def test_runtime_comparison_uses_only_live_lookup_and_native_doris() -> None:
    comparison = _runtime_comparison(
        {
            "current_runtime": {
                "status": "observed",
                "queries": [
                    {
                        "query": "find_definitions",
                        "symbol": "Thing",
                        "warm": {"p50_seconds": 0.2, "p95_seconds": 0.3},
                    }
                ],
            }
        },
        {
            "doris": {
                "status": "observed",
                "queries": [
                    {
                        "query": "find_definitions",
                        "symbol": "Thing",
                        "warm": {"p50_seconds": 0.4, "p95_seconds": 0.6},
                    },
                    {"query": "field_layout", "symbol": "Thing"},
                ],
            },
            "load_store": {"status": "observed"},
        },
    )

    assert comparison["status"] == "observed"
    assert comparison["baseline_backend"] == "prior_live_lookup"
    assert comparison["candidate_backend"] == "native_doris"
    assert comparison["excluded_paths"] == ["parquet_file_store"]
    assert comparison["queries"] == [
        {
            "query": "find_definitions",
            "symbol": "Thing",
            "prior_live_lookup": {"p50_seconds": 0.2, "p95_seconds": 0.3},
            "native_doris": {"p50_seconds": 0.4, "p95_seconds": 0.6},
            "native_doris_to_prior_p50_ratio": 2.0,
            "native_doris_to_prior_p95_ratio": 2.0,
        }
    ]

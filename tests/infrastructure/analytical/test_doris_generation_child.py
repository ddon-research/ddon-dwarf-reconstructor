"""Generation child-runner state and failure evidence tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris import (
    current_generation as generation_module,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _GenerationRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.workloads: list[object] = []

    def run(self, workload: object) -> SimpleNamespace:
        self.workloads.append(workload)
        if self.fail:
            raise RuntimeError("generation child failed")
        return SimpleNamespace(status=SimpleNamespace(value="observed"), to_dict=lambda: {})


def test_generation_child_runner_records_states_and_failures(tmp_path: Path) -> None:
    runner = _GenerationRunner()
    runs = generation_module.run_generation_workloads(
        runner,
        Path("source.elf"),
        Path("manifest.json"),
        tmp_path,
        ("rLayout",),
        1,
        30.0,
        1,
        30.0,
        1,
        1,
        1,
        True,
        500.0,
        2,
    )
    assert len(runs) == 4
    assert {run["state"] for run in runs} == {"cold", "warm", "long"}
    assert all(run["status"] == "partial" for run in runs)
    assert all(
        "DDON_DORIS_QUERY_TRACE_PATH" in dict(workload.environment) for workload in runner.workloads
    )

    workload = generation_module._generation_workload(
        Path("source.elf"),
        Path("manifest.json"),
        tmp_path / "failed",
        name="failed",
        symbol="rLayout",
        state=SimpleNamespace(value="cold"),
        timeout_seconds=30.0,
    )
    blocked = generation_module._run_one(
        _GenerationRunner(fail=True), workload, tmp_path / "failed", "rLayout", "cold", 1
    )
    assert blocked["status"] == "blocked"

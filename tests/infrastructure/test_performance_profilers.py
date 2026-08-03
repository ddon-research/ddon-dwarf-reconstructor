"""Profiler command construction and normalized method evidence tests."""

import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState, PerformanceWorkload
from ddon_dwarf_reconstructor.infrastructure.performance.profilers import (
    _cprofile_command,
    _py_spy_command,
    _pyinstrument_command,
    _pyperf_command,
    _scalene_command,
    _tracemalloc_command,
    parse_method_summaries,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_profiler_commands_wrap_the_canonical_module_workload(tmp_path: Path) -> None:
    """Each adapter preserves the target module and arguments."""
    workload = _workload(tmp_path)
    output = tmp_path / "profile.json"

    assert _cprofile_command(workload, output)[1:7] == (
        "-m",
        "cProfile",
        "-o",
        str(output),
        "-m",
        "ddon_dwarf_reconstructor.infrastructure.performance.fixture_target",
    )
    assert _pyinstrument_command(workload, output)[1:8] == (
        "-m",
        "pyinstrument",
        "-r",
        "json",
        "-o",
        str(output),
        "-m",
    )
    assert _scalene_command("scalene")(workload, output)[0:2] == ("scalene", "run")
    assert _py_spy_command("py-spy")(workload, output)[0:2] == ("py-spy", "record")
    assert _tracemalloc_command(workload, output)[1:4] == (
        "-m",
        "ddon_dwarf_reconstructor.infrastructure.performance.tracemalloc_target",
        "--output",
    )
    assert _pyperf_command(workload, output)[1:4] == ("-m", "pyperf", "command")


def test_scalene_lines_are_ranked_by_cpu_and_keep_memory_evidence(tmp_path: Path) -> None:
    """Scalene's line-oriented JSON remains method-level, status-bearing evidence."""
    path = tmp_path / "scalene.json"
    path.write_text(
        '{"files": {"fixture.py": {"lines": ['
        '{"lineno": 1, "n_cpu_percent_python": 1.0, "n_avg_mb": 4.0},'
        '{"lineno": 2, "n_cpu_percent_python": 9.0, "n_avg_mb": 2.0}'
        "]}}}",
        encoding="utf-8",
    )

    summaries, diagnostics = parse_method_summaries("scalene", path)

    assert not diagnostics
    assert summaries[0].line == 2
    assert summaries[0].cpu_percent == 9.0
    assert summaries[0].memory_bytes == 2 * 1024 * 1024


def _workload(tmp_path: Path) -> PerformanceWorkload:
    return PerformanceWorkload(
        name="fixture",
        command=(
            sys.executable,
            "-m",
            "ddon_dwarf_reconstructor.infrastructure.performance.fixture_target",
            "--iterations",
            "1",
        ),
        cwd=tmp_path,
        state=ColdWarmState.WARM,
    )

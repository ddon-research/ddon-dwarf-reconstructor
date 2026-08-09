"""Profiler command construction and normalized method evidence tests."""

import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState, PerformanceWorkload
from ddon_dwarf_reconstructor.infrastructure.performance.profilers import (
    _cprofile_command,
    _normalise_names,
    _py_spy_command,
    _pyinstrument_command,
    _pyperf_command,
    _tracemalloc_command,
    parse_method_summaries,
)
from ddon_dwarf_reconstructor.infrastructure.performance.scalene import (
    scalene_command,
    scalene_leak_metrics,
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
    scalene_run = scalene_command("scalene")(workload, output)
    assert scalene_run[0:2] == ("scalene", "run")
    assert scalene_run[2:6] == (
        "--program-path",
        str(Path(__file__).resolve().parents[2] / "src" / "ddon_dwarf_reconstructor"),
        "--profile-exclude",
        "scalene_target.py",
    )
    assert scalene_run[6:9] == ("--memory-leak-detector", "-o", str(output))
    py_spy_command = _py_spy_command("py-spy")(workload, output)
    assert py_spy_command[0:2] == ("py-spy", "record")
    assert py_spy_command[2:4] == ("--rate", "5")
    assert py_spy_command[4] == "--nonblocking"
    assert _tracemalloc_command(workload, output)[1:4] == (
        "-m",
        "ddon_dwarf_reconstructor.infrastructure.performance.tracemalloc_target",
        "--output",
    )
    assert _pyperf_command(workload, output)[1:4] == ("-m", "pyperf", "command")


def test_scalene_library_mode_profiles_external_python_libraries(tmp_path: Path) -> None:
    """The optional Scalene mode broadens scope without changing the workload."""
    command = scalene_command("scalene", profile_libraries=True)(
        _workload(tmp_path), tmp_path / "x.json"
    )

    assert command[2:6] == (
        "--profile-all",
        "--profile-system-libraries",
        "--profile-exclude",
        "scalene_target.py",
    )
    assert "--memory-leak-detector" in command


def test_scalene_library_mode_broadens_direct_script_workloads(tmp_path: Path) -> None:
    """Broad scope also applies when a workload is launched as a script."""
    workload = PerformanceWorkload(
        name="script-fixture",
        command=(sys.executable, "fixture.py", "--iterations", "1"),
        cwd=tmp_path,
        state=ColdWarmState.WARM,
    )

    command = scalene_command("scalene", profile_libraries=True)(workload, tmp_path / "x.json")

    assert command[2:4] == ("--profile-all", "--profile-system-libraries")


def test_scalene_leak_metrics_report_records(tmp_path: Path) -> None:
    """The normalized contract exposes the experimental detector result count."""
    path = tmp_path / "scalene.json"
    path.write_text(
        '{"files": {"fixture.py": {"leaks": {}}, "other.py": {"leaks": {"2": 1}}}}',
        encoding="utf-8",
    )

    metrics = scalene_leak_metrics("scalene-libraries", path)

    assert metrics[0].name == "scalene_leak_records"
    assert metrics[0].value == 1


def test_all_selector_keeps_cprofile_and_excludes_broad_scalene_scope() -> None:
    """The broad library view remains opt-in without removing cProfile."""
    assert _normalise_names(("all",)) == ("scalene", "cprofile", "pyinstrument", "py-spy")
    assert _normalise_names(("scalene-libraries",)) == ("scalene-libraries",)


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

    summaries, diagnostics = parse_method_summaries("scalene-libraries", path)

    assert not diagnostics
    assert summaries[0].profiler == "scalene-libraries"
    assert summaries[0].line == 2
    assert summaries[0].cpu_percent == 9.0
    assert summaries[0].memory_bytes == 2 * 1024 * 1024


def test_scalene_ignores_zero_cost_lines_and_reports_missing_attribution(tmp_path: Path) -> None:
    """A Scalene report must not fabricate hot lines from zero-filled source rows."""
    path = tmp_path / "scalene.json"
    path.write_text(
        '{"files": {"fixture.py": {"lines": ['
        '{"lineno": 1, "n_cpu_percent_python": 0.0, "n_cpu_percent_c": 0.0, "n_avg_mb": 0.0}'
        "]}}}",
        encoding="utf-8",
    )

    summaries, diagnostics = parse_method_summaries("scalene", path)

    assert not summaries
    assert diagnostics == ("scalene produced no non-zero CPU or memory line attribution",)


def test_scalene_ignores_module_launcher_attribution(tmp_path: Path) -> None:
    """The helper launcher must not be reported as an application hotspot."""
    path = tmp_path / "scalene.json"
    path.write_text(
        '{"files": {"scalene_target.py": {"lines": ['
        '{"lineno": 18, "n_cpu_percent_c": 50.0, "n_avg_mb": 0.0}'
        "]}}}",
        encoding="utf-8",
    )

    summaries, diagnostics = parse_method_summaries("scalene", path)

    assert not summaries
    assert diagnostics == ("scalene produced no non-zero CPU or memory line attribution",)


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

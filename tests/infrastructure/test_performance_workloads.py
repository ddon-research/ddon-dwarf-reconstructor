"""Canonical command construction for profiling workloads."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState
from ddon_dwarf_reconstructor.infrastructure.performance.workloads import (
    build_dump_index_workload,
    build_materializer_workload,
    build_reconstructor_workload,
)
from ddon_dwarf_reconstructor.performance_analytical_cli import _benchmark_dwarf_store_command

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_workload_uses_current_export_knowledge_command_tree(tmp_path: Path) -> None:
    """Profiling never falls back to the removed legacy command shape."""
    workload = build_reconstructor_workload(
        repository_root=tmp_path,
        name="rlayout",
        elf=tmp_path / "source.elf",
        symbols=("rLayout",),
        mode="export-knowledge",
        state=ColdWarmState.WARM,
        output_dir=tmp_path / "output",
        dwarf_index=tmp_path / "index.sqlite3",
        build_id="ps4-02020005",
    )

    assert workload.command[1:4] == ("-m", "ddon_dwarf_reconstructor", "export-knowledge")
    assert "--symbol" in workload.command
    assert "--output-dir" in workload.command
    assert "--generate" not in workload.command
    assert workload.environment_dict() == {"PYTHONFAULTHANDLER": "1"}


def test_dump_index_workload_uses_force_rebuild_command(tmp_path: Path) -> None:
    """Cold index evidence targets the explicit artifact rebuild command."""
    workload = build_dump_index_workload(
        repository_root=tmp_path,
        name="cold-index",
        dwarf_dump=tmp_path / "dump.zst",
        index_path=tmp_path / "index.sqlite3",
        state=ColdWarmState.COLD,
        timeout_seconds=3600,
    )

    assert workload.command[1:6] == (
        "-m",
        "ddon_dwarf_reconstructor",
        "artifacts",
        "rebuild-dump-index",
        str(tmp_path / "dump.zst"),
    )
    assert "--index-path" in workload.command
    assert workload.source_path == tmp_path / "dump.zst"


def test_materializer_workload_uses_isolated_direct_parquet_contract(tmp_path: Path) -> None:
    """Profiler probes use the same bounded writer lifecycle as production."""
    workload = build_materializer_workload(
        repository_root=tmp_path,
        name="materializer-profile",
        elf=tmp_path / "source.elf",
        output_dir=tmp_path / "store",
        max_cus=8,
        max_open_writers=16,
        parquet_layout="family",
        rotate_writers_every_cus=64,
    )

    assert workload.command[1:5] == (
        "-m",
        "ddon_dwarf_reconstructor",
        "artifacts",
        "materialize-dwarf",
    )
    assert "--no-write-jsonl" in workload.command
    assert workload.command[workload.command.index("--max-cus") + 1] == "8"
    assert workload.command[workload.command.index("--rotate-writers-every-cus") + 1] == "64"
    assert workload.environment_dict() == {"PYTHONFAULTHANDLER": "1"}


def test_workload_can_target_alternate_python_or_compiled_launcher(tmp_path: Path) -> None:
    """Runtime comparisons use the same command contract for both launch modes."""
    python_workload = build_reconstructor_workload(
        repository_root=tmp_path,
        name="free-threaded",
        elf=tmp_path / "source.elf",
        symbols=("rLayout",),
        mode="export-knowledge",
        state=ColdWarmState.WARM,
        output_dir=tmp_path / "output",
        python_executable=tmp_path / "python3.14t.exe",
    )
    launcher_workload = build_reconstructor_workload(
        repository_root=tmp_path,
        name="nuitka",
        elf=tmp_path / "source.elf",
        symbols=("rLayout",),
        mode="export-knowledge",
        state=ColdWarmState.WARM,
        output_dir=tmp_path / "output",
        launcher=tmp_path / "reconstructor.exe",
    )

    assert python_workload.command[:3] == (
        str(tmp_path / "python3.14t.exe"),
        "-m",
        "ddon_dwarf_reconstructor",
    )
    assert launcher_workload.command[0] == str(tmp_path / "reconstructor.exe")
    assert launcher_workload.command[1] == "export-knowledge"


def test_profiled_store_command_preserves_backend_query_options(tmp_path: Path) -> None:
    """The profiler wraps the same bounded benchmark command used by operators."""
    command = _benchmark_dwarf_store_command(
        elf=tmp_path / "source.elf",
        output_dir=tmp_path / "report",
        store_manifest=tmp_path / "manifest.json",
        symbols=("rLayout", "MtObject"),
        run_doris=False,
        query_existing_doris=True,
        iterations=5,
        allow_incomplete=False,
        run_knowledge_export=True,
    )

    assert tuple(command[1:6]) == (
        "-m",
        "ddon_dwarf_reconstructor",
        "performance",
        "benchmark-dwarf-store",
        str(tmp_path / "source.elf"),
    )
    assert "--query-existing-doris" in command
    assert "--run-knowledge-export" in command
    assert command[command.index("--iterations") + 1] == "5"

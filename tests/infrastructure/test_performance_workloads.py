"""Canonical command construction for profiling workloads."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState
from ddon_dwarf_reconstructor.infrastructure.performance.workloads import (
    build_dump_index_workload,
    build_reconstructor_workload,
)

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

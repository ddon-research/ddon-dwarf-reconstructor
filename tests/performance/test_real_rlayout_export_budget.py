"""Opt-in real-asset performance budget for the pilot dependency closure."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState
from ddon_dwarf_reconstructor.infrastructure.performance.runner import PerformanceRunner
from ddon_dwarf_reconstructor.infrastructure.performance.workloads import (
    build_reconstructor_workload,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.non_functional,
    pytest.mark.performance,
    pytest.mark.real_asset,
    pytest.mark.slow,
]


def test_real_rlayout_export_completes_within_warm_budget(tmp_path: Path) -> None:
    """The warm indexed rLayout export should finish within its regression budget."""
    if os.environ.get("DDON_REAL_PERFORMANCE") != "1":
        pytest.skip("set DDON_REAL_PERFORMANCE=1 to run the real ELF performance budget")
    repository_root = Path(__file__).resolve().parents[2]
    elf_path = Path(os.environ.get("DDON_REAL_ELF", repository_root / "resources" / "DDOORBIS.elf"))
    if not elf_path.exists():
        pytest.skip(f"real ELF is unavailable: {elf_path}")

    output_dir = tmp_path / "rLayout-knowledge"
    dwarf_dump = _optional_path("DDON_REAL_DWARF_DUMP")
    dwarf_index = _optional_path("DDON_REAL_DWARF_INDEX")
    orbis_objdump = _optional_path("DDON_ORBIS_OBJDUMP")
    workload = build_reconstructor_workload(
        repository_root=repository_root,
        name="real-rlayout-export",
        elf=elf_path,
        symbols=("rLayout",),
        mode="export-knowledge",
        state=ColdWarmState.WARM,
        output_dir=output_dir,
        dwarf_dump=dwarf_dump,
        dwarf_index=dwarf_index,
        build_id="ps4-02020005",
        orbis_objdump=orbis_objdump,
        timeout_seconds=30.0,
    )
    summary = PerformanceRunner(tmp_path / "performance-artifacts").run(workload)

    assert summary.return_code == 0, summary.to_dict()
    assert summary.duration_seconds is not None
    assert summary.duration_seconds < 15.0, (
        f"warm rLayout export took {summary.duration_seconds:.2f}s (budget: 15s)"
    )
    assert (output_dir / "manifest.json").exists()
    if orbis_objdump:
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["disassembly"]["tool"]["target"] == "elf64-x86-64-freebsd"
        instructions = [
            json.loads(line)
            for line in (output_dir / "instructions.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        load_id = "function:ps4-02020005:orbis:693e60"
        load_instructions = [item for item in instructions if item["function_id"] == load_id]
        assert load_instructions[0]["address"] == 0x693E60
        assert load_instructions[-1]["address"] < 0x694AE5
        assert any(item["source_file"].endswith("rLayout.cpp") for item in load_instructions)


def _optional_path(environment_name: str) -> Path | None:
    value = os.environ.get(environment_name)
    return Path(value) if value else None

"""Opt-in real-asset performance budget for the pilot dependency closure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _optional_argument(option: str, environment_name: str) -> list[str]:
    value = os.environ.get(environment_name)
    return [option, value] if value else []


@pytest.mark.performance
def test_real_rlayout_export_completes_within_warm_budget(tmp_path: Path) -> None:
    """The warm indexed rLayout export should finish within its regression budget."""
    if os.environ.get("DDON_REAL_PERFORMANCE") != "1":
        pytest.skip("set DDON_REAL_PERFORMANCE=1 to run the real ELF performance budget")
    repository_root = Path(__file__).resolve().parents[2]
    elf_path = Path(os.environ.get("DDON_REAL_ELF", repository_root / "resources" / "DDOORBIS.elf"))
    if not elf_path.exists():
        pytest.skip(f"real ELF is unavailable: {elf_path}")

    output_dir = tmp_path / "rLayout-knowledge"
    command = [
        sys.executable,
        "-m",
        "ddon_dwarf_reconstructor",
        str(elf_path),
        "--generate",
        "rLayout",
        "--export-knowledge",
        str(output_dir),
        "--build-id",
        "ps4-02020005",
    ]
    command.extend(_optional_argument("--dwarf-dump", "DDON_REAL_DWARF_DUMP"))
    command.extend(_optional_argument("--dwarf-index", "DDON_REAL_DWARF_INDEX"))
    orbis_objdump = os.environ.get("DDON_ORBIS_OBJDUMP")
    command.extend(_optional_argument("--orbis-objdump", "DDON_ORBIS_OBJDUMP"))
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    elapsed = time.perf_counter() - started

    assert result.returncode == 0, result.stdout + result.stderr
    assert elapsed < 15.0, f"warm rLayout export took {elapsed:.2f}s (budget: 15s)"
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

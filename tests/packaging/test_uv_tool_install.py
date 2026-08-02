from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.acceptance, pytest.mark.functional, pytest.mark.packaging]


def _uv_executable() -> str:
    executable = shutil.which("uv") or shutil.which("uv.exe")
    if executable is None:
        pytest.fail("uv is required for the packaging smoke test")
    return executable


def _tool_executable(bin_directory: Path) -> Path:
    name = "ddon-dwarf-reconstructor.exe" if os.name == "nt" else "ddon-dwarf-reconstructor"
    return bin_directory / name


def test_uv_tool_install_exposes_standalone_cli(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    tool_directory = tmp_path / "uv-tools"
    bin_directory = tmp_path / "uv-bin"
    environment = os.environ.copy()
    environment.update(
        {
            "UV_TOOL_DIR": str(tool_directory),
            "UV_TOOL_BIN_DIR": str(bin_directory),
            "UV_NO_PROGRESS": "1",
        }
    )

    install = subprocess.run(
        [
            _uv_executable(),
            "tool",
            "install",
            str(repository_root),
            "--python",
            "3.14.6",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    executable = _tool_executable(bin_directory)
    assert executable.is_file()

    version = subprocess.run(
        [str(executable), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert version.returncode == 0, version.stdout + version.stderr
    assert version.stdout.strip() == "0.1.0"

    help_result = subprocess.run(
        [str(executable), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "generate" in help_result.stdout
    assert "export-knowledge" in help_result.stdout
    assert "artifacts" in help_result.stdout
    assert str(repository_root / "src") not in help_result.stdout

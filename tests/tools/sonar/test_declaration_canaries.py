"""The canary runner distinguishes expected C++ rejection from tool failures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.sonar import run_declaration_canaries as canaries
from tools.sonar.msvc_validation.commands import CommandExecution

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def test_compiler_setup_failure_cannot_satisfy_expected_cpp_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "allocator-reversed.cpp"
    source.write_text("invalid", encoding="utf-8")
    monkeypatch.setattr(
        canaries,
        "run_command",
        lambda *_args, **_kwargs: CommandExecution(9001, "setup failed", ""),
    )

    result = canaries._run_one(
        source,
        "allocator-reversed",
        "c++17",
        "msvc",
        tmp_path / "results",
        tmp_path / "VsDevCmd.bat",
        tmp_path / "clang++.exe",
        10,
    )

    assert result["expected_pass"] is False
    assert result["status"] == "mismatch"


def test_truncated_clang_rejection_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "grass-owner-first.cpp"
    source.write_text("invalid", encoding="utf-8")
    monkeypatch.setattr(
        canaries,
        "run_command",
        lambda *_args, **_kwargs: CommandExecution(1, "error", "", stdout_truncated=True),
    )

    result = canaries._run_one(
        source,
        "grass-owner-first",
        "c++17",
        "clang",
        tmp_path / "results",
        tmp_path / "VsDevCmd.bat",
        tmp_path / "clang++.exe",
        10,
    )

    assert result["status"] == "mismatch"
    assert result["output_truncated"] is True


def test_unrelated_clang_failure_does_not_confirm_declaration_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "grass-owner-first.cpp"
    source.write_text("invalid", encoding="utf-8")
    monkeypatch.setattr(
        canaries,
        "run_command",
        lambda *_args, **_kwargs: CommandExecution(1, "fatal error: missing header", ""),
    )

    result = canaries._run_one(
        source,
        "grass-owner-first",
        "c++17",
        "clang",
        tmp_path / "results",
        tmp_path / "VsDevCmd.bat",
        tmp_path / "clang++.exe",
        10,
    )

    assert result["status"] == "mismatch"
    assert result["expected_diagnostic"] == "implicit instantiation of undefined template"

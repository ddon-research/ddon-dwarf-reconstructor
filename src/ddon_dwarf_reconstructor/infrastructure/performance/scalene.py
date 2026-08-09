"""Scalene command construction for application and library profiles."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ...domain.models.performance import EvidenceStatus, MetricRecord, PerformanceWorkload

SCALENE_WRAPPER_NAME = "scalene_target.py"
SCALENE_LIBRARY_PROFILER = "scalene-libraries"


def scalene_command(
    executable: str, profile_libraries: bool = False
) -> Callable[[PerformanceWorkload, Path], tuple[str, ...]]:
    """Build a Scalene command with either application or broad library scope."""

    def command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
        target = workload.command
        if len(target) >= 3 and target[1] == "-m":
            scope = (
                ("--profile-all", "--profile-system-libraries")
                if profile_libraries
                else ("--program-path", str(Path(__file__).resolve().parents[2]))
            )
            return (
                executable,
                "run",
                *scope,
                "--profile-exclude",
                SCALENE_WRAPPER_NAME,
                "--memory-leak-detector",
                "-o",
                str(path),
                str(Path(__file__).with_name(SCALENE_WRAPPER_NAME)),
                "--module",
                target[2],
                *target[3:],
            )
        scope = ("--profile-all", "--profile-system-libraries") if profile_libraries else ()
        return (
            executable,
            "run",
            *scope,
            "--memory-leak-detector",
            "-o",
            str(path),
            *target,
        )

    return command


def scalene_leak_metrics(profiler: str, path: Path | None) -> tuple[MetricRecord, ...]:
    """Return the observed count of Scalene leak records in a JSON profile."""
    if not profiler.startswith("scalene"):
        return ()
    if path is None or not path.exists():
        return ()
    payload = _read_json(path)
    if payload is None:
        return ()
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return ()
    count = sum(_file_leak_count(value) for value in files.values())
    return (MetricRecord("scalene_leak_records", count, "records", EvidenceStatus.OBSERVED),)


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, TypeError, ValueError:
        return None


def _file_leak_count(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    leaks = value.get("leaks")
    return len(leaks) if isinstance(leaks, (dict, list)) else 0

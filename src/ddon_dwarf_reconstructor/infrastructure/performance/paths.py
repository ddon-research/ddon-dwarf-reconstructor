"""Paths and atomic file helpers for external performance evidence."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

from ...core.content_hash import sha256_file
from ..artifact_io import atomic_write_text


def get_performance_artifact_dir() -> Path:
    """Return the ignored OS-local directory for raw profiler evidence."""
    configured = os.environ.get("DDON_PERFORMANCE_ARTIFACT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        # Keep raw profiles and child logs on the local temporary volume.  The
        # analytical workflow can produce large, disposable evidence bundles;
        # LOCALAPPDATA is a durable cache root and is not the requested default.
        base = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return (base / "ddon-dwarf-reconstructor" / "performance").resolve()


def get_performance_database_path(repository_root: Path | None = None) -> Path:
    """Return the tracked history database path for the current checkout."""
    root = repository_root or Path.cwd()
    return root / "resources" / "performance" / "benchmarks.sqlite3"


def write_json(path: Path, payload: object) -> None:
    """Write deterministic JSON through the atomic publication helper."""
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def git_metadata(cwd: Path) -> tuple[str, bool | None]:
    """Return the repository revision and dirty state when Git is available."""
    revision = _git_command(cwd, "rev-parse", "HEAD")
    status = _git_command(cwd, "status", "--porcelain", "--untracked-files=all")
    if revision is None:
        return "unavailable", None
    return revision, status is not None and bool(status)


def machine_profile() -> str:
    """Return a compact machine identity suitable for like-for-like comparisons."""
    return ":".join(
        (
            platform.system() or "unknown",
            platform.machine() or "unknown",
            platform.processor() or "unknown",
        )
    )


def _git_command(cwd: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


__all__ = [
    "atomic_write_text",
    "get_performance_artifact_dir",
    "get_performance_database_path",
    "git_metadata",
    "machine_profile",
    "sha256_file",
    "write_json",
]

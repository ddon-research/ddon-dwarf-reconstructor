"""Runtime identity probes for reproducible performance comparisons."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

from ...domain.models.performance import RuntimeDescriptor


def current_runtime() -> RuntimeDescriptor:
    """Describe the interpreter hosting the performance command."""
    return _descriptor(
        executable=Path(sys.executable),
        implementation=platform.python_implementation(),
        version=platform.python_version(),
        gil_enabled=_gil_enabled(),
    )


def probe_python_runtime(executable: Path) -> RuntimeDescriptor:
    """Probe a CPython executable without importing the project into it."""
    command = (
        str(executable),
        "-c",
        "import json, platform, sys; print(json.dumps({"
        "'implementation': platform.python_implementation(), "
        "'version': platform.python_version(), "
        "'gil_enabled': getattr(sys, '_is_gil_enabled', lambda: None)()"
        "}))",
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"could not probe Python runtime {executable}: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Python runtime probe failed for {executable}: {detail}")
    try:
        payload = json.loads(result.stdout)
        implementation = str(payload["implementation"])
        version = str(payload["version"])
        gil_enabled = payload.get("gil_enabled")
        if not isinstance(gil_enabled, (bool, type(None))):
            gil_enabled = None
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid Python runtime probe for {executable}") from error
    return _descriptor(executable, implementation, version, gil_enabled)


def ensure_project_importable(executable: Path, project_root: Path) -> None:
    """Reject a bare interpreter that does not have the project installed."""
    try:
        result = subprocess.run(
            (str(executable), "-c", "import ddon_dwarf_reconstructor"),
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"could not validate project import for {executable}: {error}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(
            f"{executable} cannot import ddon_dwarf_reconstructor; install the project in "
            f"that runtime ({detail})"
        )


def nuitka_runtime(executable: Path, python_version: str) -> RuntimeDescriptor:
    """Describe a compiled CPython application produced by Nuitka."""
    return RuntimeDescriptor(
        name=f"nuitka-cpython-{python_version}",
        implementation="Nuitka/CPython",
        python_version=python_version,
        gil_enabled=True,
        executable=executable.resolve(),
    )


def _descriptor(
    executable: Path,
    implementation: str,
    version: str,
    gil_enabled: bool | None,
) -> RuntimeDescriptor:
    suffix = "-free-threaded" if gil_enabled is False else ""
    return RuntimeDescriptor(
        name=f"{implementation.lower()}-{version}{suffix}",
        implementation=implementation,
        python_version=version,
        gil_enabled=gil_enabled,
        executable=executable.resolve(),
    )


def _gil_enabled() -> bool | None:
    probe = getattr(sys, "_is_gil_enabled", None)
    if not callable(probe):
        return None
    value = probe()
    return value if isinstance(value, bool) else None


__all__ = [
    "current_runtime",
    "ensure_project_importable",
    "nuitka_runtime",
    "probe_python_runtime",
]

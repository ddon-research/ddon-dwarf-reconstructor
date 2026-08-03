"""Discovery of optional and built-in performance tools."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from importlib import import_module
from importlib.util import find_spec

from ...domain.models.performance import EvidenceStatus, ToolAvailability

TOOL_NAMES = (
    "process-sampler",
    "scalene",
    "cprofile",
    "pyinstrument",
    "py-spy",
    "pyperf",
    "tracemalloc",
    "psutil",
)
_EXECUTABLES = {"scalene": "scalene", "pyinstrument": "pyinstrument", "py-spy": "py-spy"}


def discover_tools() -> tuple[ToolAvailability, ...]:
    """Probe every supported profiler without importing optional packages."""
    return tuple(_discover(name) for name in TOOL_NAMES)


def _discover(name: str) -> ToolAvailability:
    if name == "process-sampler":
        return ToolAvailability(name, sys.executable, "built-in", EvidenceStatus.OBSERVED)
    if name == "cprofile":
        return ToolAvailability(
            name, sys.executable, platform.python_version(), EvidenceStatus.OBSERVED
        )
    if name == "tracemalloc":
        return _module_availability(name, "tracemalloc")
    if name == "psutil":
        return _module_availability(name, "psutil")
    if name == "pyperf":
        return _module_availability(name, "pyperf")
    executable_name = _EXECUTABLES[name]
    executable = shutil.which(executable_name)
    if executable is None:
        return ToolAvailability(
            name, None, "unavailable", EvidenceStatus.UNAVAILABLE, "not on PATH"
        )
    return _executable_availability(name, executable)


def _module_availability(name: str, module_name: str) -> ToolAvailability:
    if find_spec(module_name) is None:
        return ToolAvailability(
            name, None, "unavailable", EvidenceStatus.UNAVAILABLE, "module is not installed"
        )
    try:
        module = import_module(module_name)
        version = str(getattr(module, "__version__", platform.python_version()))
    except (ImportError, AttributeError) as error:
        return ToolAvailability(name, None, "unavailable", EvidenceStatus.UNAVAILABLE, str(error))
    return ToolAvailability(name, sys.executable, version, EvidenceStatus.OBSERVED)


def _executable_availability(name: str, executable: str) -> ToolAvailability:
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return ToolAvailability(
            name, executable, "unavailable", EvidenceStatus.UNAVAILABLE, str(error)
        )
    version = (result.stdout or result.stderr).strip().splitlines()
    if result.returncode:
        return ToolAvailability(
            name,
            executable,
            "unavailable",
            EvidenceStatus.UNAVAILABLE,
            (version[0] if version else f"exit code {result.returncode}"),
        )
    return ToolAvailability(
        name, executable, version[0] if version else "unknown", EvidenceStatus.OBSERVED
    )


__all__ = ["TOOL_NAMES", "discover_tools"]

"""Runtime identity probes used by cross-runtime performance comparisons."""

import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.performance.runtime import probe_python_runtime

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_python_runtime_probe_reports_the_selected_interpreter() -> None:
    """The probe does not assume that the parent interpreter is the target."""
    runtime = probe_python_runtime(Path(sys.executable))

    assert runtime.python_version == ".".join(str(part) for part in sys.version_info[:3])
    assert runtime.executable == Path(sys.executable).resolve()

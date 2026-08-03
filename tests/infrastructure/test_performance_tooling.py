"""Tool discovery and missing-counter evidence tests."""

import psutil
import pytest

from ddon_dwarf_reconstructor.domain.models.performance import EvidenceStatus
from ddon_dwarf_reconstructor.infrastructure.performance.runner import _process_values
from ddon_dwarf_reconstructor.infrastructure.performance.tooling import discover_tools

pytestmark = [pytest.mark.unit, pytest.mark.non_functional]


def test_tool_discovery_always_reports_builtin_sampler_and_profiler() -> None:
    """Optional tools may vary, but built-in evidence is always discoverable."""
    tools = {tool.name: tool for tool in discover_tools()}

    assert tools["process-sampler"].status == EvidenceStatus.OBSERVED
    assert tools["cprofile"].status == EvidenceStatus.OBSERVED
    assert tools["tracemalloc"].status == EvidenceStatus.OBSERVED


def test_process_values_preserves_missing_io_counters() -> None:
    """Access-denied I/O counters are unavailable rather than fabricated as zero."""
    process = _ProcessWithoutIo()

    values = _process_values(process)

    assert values is not None
    assert values[:4] == (1.0, 2.0, 3, 4)
    assert values[4] is None


class _ProcessWithoutIo:
    def cpu_times(self):
        return type("Cpu", (), {"user": 1.0, "system": 2.0})()

    def memory_info(self):
        return type("Memory", (), {"rss": 3, "vms": 4})()

    def io_counters(self):
        raise psutil.AccessDenied(pid=1)

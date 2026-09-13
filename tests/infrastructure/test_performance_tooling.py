"""Tool discovery and missing-counter evidence tests."""

import psutil
import pytest

from ddon_dwarf_reconstructor.domain.models.performance import EvidenceStatus
from ddon_dwarf_reconstructor.infrastructure.performance.process_accounting import (
    _process_values,
    _ProcessAccounting,
    _ProcessObservation,
)
from ddon_dwarf_reconstructor.infrastructure.performance.tooling import discover_tools

pytestmark = [pytest.mark.unit, pytest.mark.non_functional]


def test_tool_discovery_always_reports_builtin_sampler_and_profiler() -> None:
    """Optional tools may vary, but built-in evidence is always discoverable."""
    tools = {tool.name: tool for tool in discover_tools()}

    assert tools["process-sampler"].status == EvidenceStatus.OBSERVED
    assert tools["cprofile"].status == EvidenceStatus.OBSERVED
    assert tools["tracemalloc"].status == EvidenceStatus.OBSERVED
    assert tools["nuitka"].status == EvidenceStatus.OBSERVED


def test_process_values_preserves_missing_io_counters() -> None:
    """Access-denied I/O counters are unavailable rather than fabricated as zero."""
    process = _ProcessWithoutIo()

    values = _process_values(process)

    assert values is not None
    assert values[:4] == (1.0, 2.0, 3, 4)
    assert values[4] is None


def test_process_accounting_retains_short_lived_descendant_deltas() -> None:
    """Counters remain measurable after a child disappears from the process tree."""
    accounting = _ProcessAccounting()
    accounting.record(
        [
            _ProcessObservation((10, 1.0), (1.0, 2.0, 10, 20, (100, 200, 3, 4))),
            _ProcessObservation((11, 2.0), (3.0, 4.0, 30, 40, (300, 400, 5, 6))),
        ]
    )
    accounting.record(
        [
            _ProcessObservation((10, 1.0), (2.0, 3.0, 15, 25, (150, 260, 4, 5))),
            _ProcessObservation((11, 2.0), (4.0, 6.0, 50, 70, (400, 500, 7, 9))),
        ]
    )
    accounting.record([_ProcessObservation((10, 1.0), (2.0, 3.0, 15, 25, (150, 260, 4, 5)))])

    totals = accounting.totals()

    assert totals.cpu_user_seconds == 2.0
    assert totals.cpu_system_seconds == 3.0
    assert totals.read_bytes == 150
    assert totals.write_bytes == 160
    assert totals.read_count == 3
    assert totals.write_count == 4


class _ProcessWithoutIo:
    def cpu_times(self):
        return type("Cpu", (), {"user": 1.0, "system": 2.0})()

    def memory_info(self):
        return type("Memory", (), {"rss": 3, "vms": 4})()

    def io_counters(self):
        raise psutil.AccessDenied(pid=1)

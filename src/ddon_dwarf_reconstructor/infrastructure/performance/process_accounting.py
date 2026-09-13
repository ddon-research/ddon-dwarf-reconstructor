"""Process-tree sampling and lifetime counter accounting for performance runs."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import psutil

CounterValues = tuple[float, float, int, int, tuple[int, int, int, int] | None]
ProcessIdentity = tuple[int, float | None]


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    """Aggregated process-tree counters at one sampling point."""

    observed_at: float
    cpu_user_seconds: float
    cpu_system_seconds: float
    rss_bytes: int
    vms_bytes: int
    read_bytes: int | None
    write_bytes: int | None
    read_count: int | None
    write_count: int | None

    def to_dict(self) -> dict[str, int | float | None]:
        """Return one bounded JSONL sample."""
        return {
            "observed_at": self.observed_at,
            "cpu_user_seconds": self.cpu_user_seconds,
            "cpu_system_seconds": self.cpu_system_seconds,
            "rss_bytes": self.rss_bytes,
            "vms_bytes": self.vms_bytes,
            "read_bytes": self.read_bytes,
            "write_bytes": self.write_bytes,
            "read_count": self.read_count,
            "write_count": self.write_count,
        }


@dataclass(frozen=True, slots=True)
class ProcessTotals:
    """Lifetime deltas for every process observed during one workload."""

    cpu_user_seconds: float | None
    cpu_system_seconds: float | None
    read_bytes: int | None
    write_bytes: int | None
    read_count: int | None
    write_count: int | None


@dataclass(frozen=True, slots=True)
class _ProcessObservation:
    identity: ProcessIdentity
    values: CounterValues


class _ProcessAccounting:
    """Retain counters for descendants that exit before the workload does."""

    def __init__(self) -> None:
        self._first: dict[ProcessIdentity, CounterValues] = {}
        self._last: dict[ProcessIdentity, CounterValues] = {}

    def record(self, observations: list[_ProcessObservation]) -> None:
        for observation in observations:
            self._first.setdefault(observation.identity, observation.values)
            self._last[observation.identity] = observation.values

    def totals(self) -> ProcessTotals:
        cpu_user, cpu_system = _cpu_totals(self._first, self._last)
        io_totals = _io_totals(self._first, self._last)
        return ProcessTotals(
            cpu_user_seconds=cpu_user,
            cpu_system_seconds=cpu_system,
            read_bytes=None if io_totals is None else io_totals[0],
            write_bytes=None if io_totals is None else io_totals[1],
            read_count=None if io_totals is None else io_totals[2],
            write_count=None if io_totals is None else io_totals[3],
        )


def _cpu_totals(
    first_values: dict[ProcessIdentity, CounterValues],
    last_values: dict[ProcessIdentity, CounterValues],
) -> tuple[float | None, float | None]:
    if not first_values:
        return None, None
    return (
        sum(
            max(0.0, last_values[identity][0] - first[0])
            for identity, first in first_values.items()
        ),
        sum(
            max(0.0, last_values[identity][1] - first[1])
            for identity, first in first_values.items()
        ),
    )


def _io_totals(
    first_values: dict[ProcessIdentity, CounterValues],
    last_values: dict[ProcessIdentity, CounterValues],
) -> tuple[int, int, int, int] | None:
    paired: list[tuple[tuple[int, int, int, int], tuple[int, int, int, int]]] = []
    for identity, first in first_values.items():
        pair = _io_pair(first, last_values[identity])
        if pair is not None:
            paired.append(pair)
    if not paired:
        return None
    return (
        sum(max(0, last[0] - first[0]) for first, last in paired),
        sum(max(0, last[1] - first[1]) for first, last in paired),
        sum(max(0, last[2] - first[2]) for first, last in paired),
        sum(max(0, last[3] - first[3]) for first, last in paired),
    )


def _io_pair(
    first: CounterValues, last: CounterValues
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    if first[4] is None or last[4] is None:
        return None
    return first[4], last[4]


def snapshot_process_tree(
    pid: int, *, accounting: _ProcessAccounting | None = None
) -> ProcessSnapshot | None:
    """Capture one live tree and optionally add its counters to run accounting."""
    processes = _process_tree(pid)
    if processes is None:
        return None
    observations = _process_observations(processes)
    if not observations:
        return None
    if accounting is not None:
        accounting.record(observations)
    return _build_snapshot([observation.values for observation in observations])


def _process_tree(pid: int) -> list[psutil.Process] | None:
    try:
        root = psutil.Process(pid)
        return [root, *root.children(recursive=True)]
    except psutil.Error, OSError:
        return None


def _process_observations(processes: list[psutil.Process]) -> list[_ProcessObservation]:
    observations: list[_ProcessObservation] = []
    for process in processes:
        values = _process_values(process)
        if values is None:
            continue
        observations.append(_ProcessObservation(_process_identity(process), values))
    return observations


def _process_identity(process: psutil.Process) -> ProcessIdentity:
    try:
        return process.pid, process.create_time()
    except psutil.Error, OSError:
        return process.pid, None


def _build_snapshot(values: list[CounterValues]) -> ProcessSnapshot:
    io_values = [value[4] for value in values if value[4] is not None]
    return ProcessSnapshot(
        monotonic(),
        sum(value[0] for value in values),
        sum(value[1] for value in values),
        sum(value[2] for value in values),
        sum(value[3] for value in values),
        _sum_io(io_values, 0),
        _sum_io(io_values, 1),
        _sum_io(io_values, 2),
        _sum_io(io_values, 3),
    )


def _process_values(process: psutil.Process) -> CounterValues | None:
    try:
        cpu = process.cpu_times()
        memory = process.memory_info()
    except psutil.Error, OSError:
        return None
    try:
        counters = process.io_counters()
    except psutil.Error, OSError:
        counters = None
    io = (
        None
        if counters is None
        else (counters.read_bytes, counters.write_bytes, counters.read_count, counters.write_count)
    )
    return cpu.user, cpu.system, memory.rss, memory.vms, io


def _sum_io(values: list[tuple[int, int, int, int]], index: int) -> int | None:
    return sum(value[index] for value in values) if values else None


__all__ = ["ProcessSnapshot", "ProcessTotals", "snapshot_process_tree"]

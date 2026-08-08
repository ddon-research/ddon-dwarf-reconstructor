"""Shared process and distribution measurements for analytical benchmarks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

import psutil

from .optional import import_optional


def measure(operation: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    """Run an operation while recording process and wall-clock deltas."""
    before = _process_snapshot()
    started = perf_counter()
    value = operation()
    after = _process_snapshot()
    return value, {
        "wall_seconds": perf_counter() - started,
        "cpu_user_seconds": after["cpu_user_seconds"] - before["cpu_user_seconds"],
        "cpu_system_seconds": after["cpu_system_seconds"] - before["cpu_system_seconds"],
        "rss_bytes": after["rss_bytes"],
        "vms_bytes": after["vms_bytes"],
        "rss_delta_bytes": after["rss_bytes"] - before["rss_bytes"],
        "read_bytes": after["read_bytes"] - before["read_bytes"],
        "write_bytes": after["write_bytes"] - before["write_bytes"],
    }


def _process_snapshot() -> dict[str, float]:
    process = psutil.Process()
    memory = process.memory_info()
    cpu = process.cpu_times()
    io = process.io_counters()
    return {
        "rss_bytes": float(memory.rss),
        "vms_bytes": float(memory.vms),
        "cpu_user_seconds": cpu.user,
        "cpu_system_seconds": cpu.system,
        "read_bytes": float(io.read_bytes),
        "write_bytes": float(io.write_bytes),
    }


def distribution(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize measured wall-clock samples using deterministic percentiles."""
    values = sorted(float(sample["wall_seconds"]) for sample in samples)
    return {
        "samples": len(values),
        "p50_seconds": _percentile(values, 0.50),
        "p95_seconds": _percentile(values, 0.95),
        "p99_seconds": _percentile(values, 0.99),
        "min_seconds": values[0] if values else None,
        "max_seconds": values[-1] if values else None,
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]


def row_group_count(parquet_files: tuple[Path, ...]) -> int:
    """Count physical Parquet row groups without loading table rows."""
    parquet = import_optional("pyarrow.parquet", "analytical")
    return sum(int(parquet.ParquetFile(path).metadata.num_row_groups) for path in parquet_files)

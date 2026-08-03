"""Deterministic JSON, CSV, and Markdown exports for benchmark history."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .history import HistoryRow, HistoryStore
from .paths import atomic_write_text


def export_history(
    store: HistoryStore,
    output_dir: Path,
    *,
    markdown_path: Path | None = None,
    workload: str | None = None,
) -> tuple[Path, Path, Path | None]:
    """Write stable history exports and return their paths."""
    payload = store.export_payload(workload)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark-history.json"
    csv_path = output_dir / "benchmark-history.csv"
    atomic_write_text(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    atomic_write_text(csv_path, _csv_text(tuple(store.rows(workload))))
    if markdown_path is not None:
        atomic_write_text(markdown_path, _markdown_text(tuple(store.rows(workload))))
    return json_path, csv_path, markdown_path


def _csv_text(rows: tuple[HistoryRow, ...]) -> str:
    metric_names = sorted({name for row in rows for name in row.metrics})
    fields = [
        "run_id",
        "workload",
        "state",
        "status",
        "started_at",
        "duration_seconds",
        "return_code",
        "git_revision",
        "git_dirty",
        "python_version",
        "platform",
        "machine_profile",
        "source_identity",
        "configuration_fingerprint",
        "profiler_mode",
        *[f"metric_{name}" for name in metric_names],
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        values = row.to_dict()
        for name in metric_names:
            metric = row.metrics.get(name, {})
            values[f"metric_{name}"] = metric.get("value")
        writer.writerow({field: values.get(field, "") for field in fields})
    return stream.getvalue()


def _markdown_text(rows: tuple[HistoryRow, ...]) -> str:
    latest = _latest(rows)
    lines = [
        "# Benchmark history",
        "",
        "This page is generated from `resources/performance/benchmarks.sqlite3`. Raw profiler "
        "outputs remain in the OS-local performance artifact directory.",
        "",
        "Evidence statuses are `observed`, `partial`, `unavailable`, `blocked`, or "
        "`not_observed`. Real-asset rows are report-only; deterministic fixture budgets are "
        "gated by their explicit performance command.",
        "",
        "## Latest like-for-like baselines",
        "",
        "| Workload | State | Profiler | Status | Wall time (s) | Peak RSS (MiB) | Read (MiB) | Write (MiB) | Started |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    if latest:
        lines.extend(_markdown_row(row) for row in latest)
    else:
        lines.append("| No runs recorded | — | — | not_observed | — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## Latest like-for-like deltas",
            "",
            "| Workload | State | Profiler | Status | Wall delta (s) | RSS delta (MiB) | Read delta (MiB) | Write delta (MiB) |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    deltas = _delta_rows(rows)
    lines.extend(deltas or ["| No compatible prior run | — | — | not_observed | — | — | — | — |"])
    lines.extend(
        [
            "",
            "## Tool availability",
            "",
            "| Tool | Status | Version | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    tool_rows = _tool_rows(rows)
    lines.extend(tool_rows or ["| No profiler artifacts recorded | not_observed | — | — |"])
    lines.extend(
        [
            "",
            "## Method-level evidence",
            "",
            "The database retains normalized top-N method or line summaries. Follow each run's "
            "manifest path for the checksummed raw profile when it is available.",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_row(row: HistoryRow) -> str:
    return "| {workload} | {state} | {profiler} | {status} | {wall} | {rss} | {read} | {write} | {started} |".format(
        workload=row.workload,
        state=row.state,
        profiler=row.profiler_mode,
        status=row.status,
        wall=_metric(row, "wall_time_seconds", scale=1),
        rss=_metric(row, "peak_rss_bytes", scale=1024 * 1024),
        read=_metric(row, "read_bytes", scale=1024 * 1024),
        write=_metric(row, "write_bytes", scale=1024 * 1024),
        started=row.started_at,
    )


def _delta_rows(rows: tuple[HistoryRow, ...]) -> list[str]:
    groups: dict[tuple[str, ...], list[HistoryRow]] = {}
    for row in rows:
        key = (
            row.workload,
            row.state,
            row.source_identity or "",
            row.python_version,
            row.platform_name,
            row.machine_profile,
            row.configuration_fingerprint,
            row.profiler_mode,
        )
        groups.setdefault(key, []).append(row)
    result: list[str] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: (item.started_at, item.run_id))
        if len(ordered) < 2:
            continue
        baseline, candidate = ordered[-2:]
        status = (
            "observed" if baseline.status == candidate.status == "observed" else candidate.status
        )
        result.append(
            "| {workload} | {state} | {profiler} | {status} | {wall} | {rss} | {read} | {write} |".format(
                workload=candidate.workload,
                state=candidate.state,
                profiler=candidate.profiler_mode,
                status=status,
                wall=_delta_metric(baseline, candidate, "wall_time_seconds", 1),
                rss=_delta_metric(baseline, candidate, "peak_rss_bytes", 1024 * 1024),
                read=_delta_metric(baseline, candidate, "read_bytes", 1024 * 1024),
                write=_delta_metric(baseline, candidate, "write_bytes", 1024 * 1024),
            )
        )
    return sorted(result)


def _delta_metric(baseline: HistoryRow, candidate: HistoryRow, name: str, scale: int) -> str:
    old = baseline.metrics.get(name, {}).get("value")
    new = candidate.metrics.get(name, {}).get("value")
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return "—"
    delta = new - old
    return f"{delta / scale:.3f}" if scale != 1 else f"{delta:.3f}"


def _metric(row: HistoryRow, name: str, *, scale: int) -> str:
    value = row.metrics.get(name, {}).get("value")
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value / scale:.3f}" if scale != 1 else f"{value:.3f}"


def _latest(rows: tuple[HistoryRow, ...]) -> tuple[HistoryRow, ...]:
    latest: dict[tuple[str, ...], HistoryRow] = {}
    for row in rows:
        key = (
            row.workload,
            row.state,
            row.source_identity or "",
            row.python_version,
            row.platform_name,
            row.machine_profile,
            row.configuration_fingerprint,
            row.profiler_mode,
        )
        latest[key] = row
    return tuple(
        sorted(latest.values(), key=lambda item: (item.workload, item.state, item.profiler_mode))
    )


def _tool_rows(rows: tuple[HistoryRow, ...]) -> list[str]:
    tools: dict[str, tuple[str, str, str]] = {
        name: ("not_observed", "—", "no artifact recorded")
        for name in (
            "process-sampler",
            "cprofile",
            "pyinstrument",
            "pyperf",
            "py-spy",
            "scalene",
            "tracemalloc",
            "psutil",
        )
    }
    for row in rows:
        for artifact in row.artifacts:
            name = str(artifact.get("profiler", "unknown"))
            status = str(artifact.get("status", "unknown"))
            version = str(artifact.get("tool_version", "unknown"))
            detail = str(artifact.get("detail", "")) or "—"
            current = tools.get(name)
            if current is None or _status_rank(status) >= _status_rank(current[0]):
                tools[name] = (status, version, detail)
    return [
        f"| {name} | {status} | {version} | {detail} |"
        for name, (status, version, detail) in sorted(tools.items())
    ]


def _status_rank(status: str) -> int:
    """Prefer concrete observed evidence over an empty default row."""
    return {
        "not_observed": 0,
        "unavailable": 1,
        "blocked": 2,
        "partial": 3,
        "observed": 4,
    }.get(status, 1)


__all__ = ["export_history"]

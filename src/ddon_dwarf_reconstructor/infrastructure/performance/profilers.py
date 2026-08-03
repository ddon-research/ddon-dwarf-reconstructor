"""Layered profiler commands and method-summary parsers."""

from __future__ import annotations

import json
import pstats
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from statistics import fmean, pstdev
from typing import cast

from ...domain.models.performance import (
    EvidenceStatus,
    MethodSummary,
    MetricRecord,
    PerformanceWorkload,
    ProfileArtifact,
    RunSummary,
    ToolAvailability,
)
from .runner import PerformanceRunner
from .tooling import discover_tools


class PerformanceProfiler:
    """Run selected optional profilers around the same target workload."""

    def __init__(self, runner: PerformanceRunner) -> None:
        self.runner = runner

    def profile(
        self, workload: PerformanceWorkload, profilers: tuple[str, ...]
    ) -> tuple[RunSummary, ...]:
        """Run each requested profiler independently for comparable evidence."""
        names = _normalise_names(profilers)
        availability = {tool.name: tool for tool in discover_tools()}
        summaries = [self._profile_one(workload, name, availability) for name in names]
        return tuple(summaries)

    def _profile_one(
        self,
        workload: PerformanceWorkload,
        name: str,
        availability: dict[str, ToolAvailability],
    ) -> RunSummary:
        tool = availability.get(name)
        if tool is None:
            return _unavailable_summary(workload, name, "unknown profiler")
        if tool.status != EvidenceStatus.OBSERVED:
            return _unavailable_summary(workload, name, tool.detail)
        if name == "process-sampler":
            return self.runner.run(workload)
        spec = _spec(name, tool)
        summary = self.runner.run(
            workload,
            command_factory=lambda path, spec=spec: spec.command(workload, path),
            profiler_name=name,
            profile_format=spec.output_format,
            profile_filename=spec.filename,
            tool_version=tool.version,
        )
        enriched = _enrich_summary(summary, name, _artifact_path(summary, name))
        self.runner.publish(enriched)
        return enriched


class _ProfilerSpec:
    """Private command construction details for one profiler."""

    def __init__(
        self,
        name: str,
        filename: str,
        output_format: str,
        command: Callable[[PerformanceWorkload, Path], tuple[str, ...]],
    ):
        self.name = name
        self.filename = filename
        self.output_format = output_format
        self.command = command


def _spec(name: str, tool: ToolAvailability) -> _ProfilerSpec:
    executable = tool.executable or name
    if name == "cprofile":
        return _ProfilerSpec(name, "cprofile.prof", "pstats", _cprofile_command)
    if name == "pyinstrument":
        return _ProfilerSpec(name, "pyinstrument.json", "json", _pyinstrument_command)
    if name == "py-spy":
        return _ProfilerSpec(
            name, "py-spy.speedscope.json", "speedscope", _py_spy_command(executable)
        )
    if name == "scalene":
        return _ProfilerSpec(name, "scalene.json", "json", _scalene_command(executable))
    if name == "tracemalloc":
        return _ProfilerSpec(name, "tracemalloc.json", "json", _tracemalloc_command)
    if name == "pyperf":
        return _ProfilerSpec(name, "pyperf.json", "json", _pyperf_command)
    return _ProfilerSpec(name, f"{name}.json", "json", lambda workload, path: workload.command)


def _artifact_path(summary: RunSummary, profiler: str) -> Path | None:
    return next((item.path for item in summary.artifacts if item.profiler == profiler), None)


def _enrich_summary(summary: RunSummary, profiler: str, path: Path | None) -> RunSummary:
    method_summaries, diagnostics = parse_method_summaries(profiler, path)
    pyperf_metrics, pyperf_diagnostics = parse_pyperf_metrics(
        path if profiler == "pyperf" else None
    )
    allocation_metrics, allocation_diagnostics = parse_allocation_metrics(profiler, path)
    return replace(
        summary,
        metrics=(*summary.metrics, *pyperf_metrics, *allocation_metrics),
        method_summaries=method_summaries,
        diagnostics=(
            *summary.diagnostics,
            *diagnostics,
            *pyperf_diagnostics,
            *allocation_diagnostics,
        ),
    )


def _cprofile_command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
    command = workload.command
    if len(command) >= 3 and command[1] == "-m":
        return (
            sys.executable,
            "-m",
            "cProfile",
            "-o",
            str(path),
            "-m",
            command[2],
            *command[3:],
        )
    return (sys.executable, "-m", "cProfile", "-o", str(path), *command)


def _pyinstrument_command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
    command = workload.command
    if len(command) >= 3 and command[1] == "-m":
        return (
            sys.executable,
            "-m",
            "pyinstrument",
            "-r",
            "json",
            "-o",
            str(path),
            "-m",
            command[2],
            *command[3:],
        )
    return (sys.executable, "-m", "pyinstrument", "-r", "json", "-o", str(path), *command)


def _scalene_command(executable: str) -> Callable[[PerformanceWorkload, Path], tuple[str, ...]]:
    def command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
        target = workload.command
        if len(target) >= 3 and target[1] == "-m":
            return (
                executable,
                "run",
                "-o",
                str(path),
                str(Path(__file__).with_name("scalene_target.py")),
                "--module",
                target[2],
                *target[3:],
            )
        return (executable, "run", "-o", str(path), *target)

    return command


def _py_spy_command(executable: str) -> Callable[[PerformanceWorkload, Path], tuple[str, ...]]:
    def command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
        return (
            executable,
            "record",
            "--output",
            str(path),
            "--format",
            "speedscope",
            "--",
            *workload.command,
        )

    return command


def _tracemalloc_command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
    target = workload.command
    if len(target) < 3 or target[1] != "-m":
        return target
    return (
        sys.executable,
        "-m",
        "ddon_dwarf_reconstructor.infrastructure.performance.tracemalloc_target",
        "--output",
        str(path),
        "--module",
        target[2],
        *target[3:],
    )


def _pyperf_command(workload: PerformanceWorkload, path: Path) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "pyperf",
        "command",
        "--fast",
        "-p",
        "1",
        "-n",
        "3",
        "-w",
        "1",
        "-o",
        str(path),
        *workload.command,
    )


def parse_method_summaries(
    profiler: str, path: Path | None, *, limit: int = 20
) -> tuple[tuple[MethodSummary, ...], tuple[str, ...]]:
    """Normalize supported profiler output into bounded method summaries."""
    if path is None or not path.exists():
        return (), (f"{profiler} method output is unavailable",)
    try:
        if profiler == "cprofile":
            return _parse_cprofile(path, limit), ()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if profiler == "scalene":
            return _parse_scalene(payload, limit), ()
        if profiler == "pyinstrument":
            return _parse_pyinstrument(payload, limit), ()
        if profiler == "py-spy":
            return _parse_speedscope(payload, limit), ()
        if profiler == "tracemalloc":
            return _parse_tracemalloc(payload, limit), ()
        return (), ()
    except (EOFError, OSError, ValueError, KeyError, TypeError) as error:
        return (), (f"{profiler} method output could not be parsed: {error}",)


def parse_pyperf_metrics(path: Path | None) -> tuple[tuple[MetricRecord, ...], tuple[str, ...]]:
    """Extract mean and population deviation from a pyperf JSON result."""
    if path is None or not path.exists():
        return (), ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = _pyperf_values(payload)
        if not values:
            return (), ("pyperf result contained no measured values",)
        return (
            (
                MetricRecord(
                    "pyperf_mean_seconds", fmean(values), "seconds", EvidenceStatus.OBSERVED
                ),
                MetricRecord(
                    "pyperf_stddev_seconds", pstdev(values), "seconds", EvidenceStatus.OBSERVED
                ),
                MetricRecord("pyperf_value_count", len(values), "values", EvidenceStatus.OBSERVED),
            ),
            (),
        )
    except (OSError, TypeError, ValueError, KeyError) as error:
        return (), (f"pyperf result could not be parsed: {error}",)


def _pyperf_values(payload: object) -> list[float]:
    if not isinstance(payload, dict) or not isinstance(payload.get("benchmarks"), list):
        return []
    values: list[float] = []
    for benchmark in payload["benchmarks"]:
        values.extend(_benchmark_values(benchmark))
    return values


def _benchmark_values(benchmark: object) -> list[float]:
    if not isinstance(benchmark, dict) or not isinstance(benchmark.get("runs"), list):
        return []
    values: list[float] = []
    for run in benchmark["runs"]:
        values.extend(_run_values(run))
    return values


def _run_values(run: object) -> list[float]:
    if not isinstance(run, dict) or not isinstance(run.get("values"), list):
        return []
    return [value for value in run["values"] if isinstance(value, (int, float))]


def parse_allocation_metrics(
    profiler: str, path: Path | None
) -> tuple[tuple[MetricRecord, ...], tuple[str, ...]]:
    """Read current and peak traced-Python memory from the tracemalloc wrapper."""
    if profiler != "tracemalloc" or path is None or not path.exists():
        return (), ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        current = payload.get("current_bytes") if isinstance(payload, dict) else None
        peak = payload.get("peak_bytes") if isinstance(payload, dict) else None
        if not isinstance(current, int) or not isinstance(peak, int):
            return (), ("tracemalloc result contained no current/peak values",)
        return (
            (
                MetricRecord("traced_current_bytes", current, "bytes", EvidenceStatus.OBSERVED),
                MetricRecord("traced_peak_bytes", peak, "bytes", EvidenceStatus.OBSERVED),
            ),
            (),
        )
    except (OSError, TypeError, ValueError) as error:
        return (), (f"tracemalloc result could not be parsed: {error}",)


def _parse_cprofile(path: Path, limit: int) -> tuple[MethodSummary, ...]:
    stats = pstats.Stats(str(path))
    raw_stats = vars(stats).get("stats", {})
    stats_data = cast(dict[tuple[str, int, str], tuple[int, int, float, float, object]], raw_stats)
    rows = sorted(stats_data.items(), key=lambda item: (-item[1][3], item[0]))[:limit]
    return tuple(
        MethodSummary(
            profiler="cprofile",
            name=key[2],
            file=key[0],
            line=key[1] if isinstance(key[1], int) else None,
            total_seconds=values[3],
            self_seconds=values[2],
            call_count=values[0],
            rank=index,
        )
        for index, (key, values) in enumerate(rows, 1)
    )


def _parse_scalene(payload: object, limit: int) -> tuple[MethodSummary, ...]:
    candidates: list[MethodSummary] = []
    if isinstance(payload, dict) and isinstance(payload.get("files"), dict):
        _collect_scalene_files(payload["files"], candidates)
    else:
        _collect_scalene(payload, candidates)
    candidates.sort(
        key=lambda item: (
            -(item.cpu_percent or 0),
            -(item.memory_bytes or 0),
            item.file or "",
            item.line or 0,
            item.name,
        )
    )
    return tuple(replace(item, rank=index) for index, item in enumerate(candidates[:limit], 1))


def _collect_scalene(value: object, candidates: list[MethodSummary]) -> None:
    if isinstance(value, dict):
        summary = _scalene_summary(value)
        if summary is not None:
            candidates.append(summary)
        for child in value.values():
            _collect_scalene(child, candidates)
    elif isinstance(value, list):
        for child in value:
            _collect_scalene(child, candidates)


def _scalene_summary(value: dict[object, object]) -> MethodSummary | None:
    name = value.get("function") or value.get("name")
    file_name = value.get("filename") or value.get("file")
    if not isinstance(name, str) or not isinstance(file_name, str):
        return None
    cpu = _number(value.get("cpu_percent")) or _number(value.get("n_cpu_percent"))
    memory = _number(value.get("memory_bytes"))
    return MethodSummary(
        profiler="scalene",
        name=name,
        file=file_name,
        line=_integer(value.get("line")),
        total_seconds=None,
        memory_bytes=int(memory) if memory is not None else None,
        cpu_percent=cpu,
    )


def _collect_scalene_files(files: dict[object, object], candidates: list[MethodSummary]) -> None:
    for file_name, payload in files.items():
        if not isinstance(file_name, str) or not isinstance(payload, dict):
            continue
        lines = payload.get("lines")
        if isinstance(lines, list):
            for line in lines:
                summary = _scalene_line_summary(file_name, line)
                if summary is not None:
                    candidates.append(summary)


def _scalene_line_summary(file_name: str, value: object) -> MethodSummary | None:
    if not isinstance(value, dict) or not isinstance(value.get("lineno"), int):
        return None
    python_cpu = _number(value.get("n_cpu_percent_python")) or 0.0
    native_cpu = _number(value.get("n_cpu_percent_c")) or 0.0
    memory_mb = _number(value.get("n_avg_mb"))
    return MethodSummary(
        profiler="scalene",
        name=f"line {value['lineno']}",
        file=file_name,
        line=value["lineno"],
        total_seconds=None,
        memory_bytes=int(memory_mb * 1024 * 1024) if memory_mb is not None else None,
        cpu_percent=python_cpu + native_cpu,
    )


def _parse_pyinstrument(payload: object, limit: int) -> tuple[MethodSummary, ...]:
    candidates: list[MethodSummary] = []
    root = payload.get("root_frame") if isinstance(payload, dict) else payload
    _collect_pyinstrument(root, candidates)
    candidates.sort(key=lambda item: (-(item.total_seconds or 0), item.file or "", item.name))
    return tuple(replace(item, rank=index) for index, item in enumerate(candidates[:limit], 1))


def _collect_pyinstrument(value: object, candidates: list[MethodSummary]) -> None:
    if not isinstance(value, dict):
        if isinstance(value, list):
            for child in value:
                _collect_pyinstrument(child, candidates)
        return
    function = value.get("function")
    if isinstance(function, str):
        candidates.append(
            MethodSummary(
                profiler="pyinstrument",
                name=function,
                file=value.get("file_path") if isinstance(value.get("file_path"), str) else None,
                line=_integer(value.get("line_number")),
                total_seconds=_number(value.get("time")),
            )
        )
    for child in value.get("children", []):
        _collect_pyinstrument(child, candidates)


def _parse_speedscope(payload: object, limit: int) -> tuple[MethodSummary, ...]:
    frames = _speedscope_frames(payload)
    if frames is None:
        return ()
    counts = _speedscope_counts(payload)
    rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    result: list[MethodSummary] = []
    for rank, (frame_index, count) in enumerate(rows, 1):
        frame = frames[frame_index] if 0 <= frame_index < len(frames) else {}
        name = frame.get("name") if isinstance(frame, dict) else None
        if isinstance(name, str):
            result.append(MethodSummary("py-spy", name, rank=rank, call_count=count))
    return tuple(result)


def _parse_tracemalloc(payload: object, limit: int) -> tuple[MethodSummary, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("top"), list):
        return ()
    result: list[MethodSummary] = []
    for rank, item in enumerate(payload["top"][:limit], 1):
        if not isinstance(item, dict):
            continue
        traceback = item.get("traceback")
        size = item.get("size_bytes")
        if isinstance(traceback, str) and isinstance(size, int):
            result.append(MethodSummary("tracemalloc", traceback, memory_bytes=size, rank=rank))
    return tuple(result)


def _speedscope_frames(payload: object) -> list[object] | None:
    if not isinstance(payload, dict):
        return None
    shared = payload.get("shared")
    frames = shared.get("frames") if isinstance(shared, dict) else None
    return frames if isinstance(frames, list) else None


def _speedscope_counts(payload: object) -> dict[int, int]:
    if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), list):
        return {}
    counts: dict[int, int] = {}
    for profile in payload["profiles"]:
        if not isinstance(profile, dict) or not isinstance(profile.get("samples"), list):
            continue
        _count_profile_samples(profile["samples"], counts)
    return counts


def _count_profile_samples(samples: list[object], counts: dict[int, int]) -> None:
    for sample in samples:
        if not isinstance(sample, list):
            continue
        for frame in sample:
            if isinstance(frame, int):
                counts[frame] = counts.get(frame, 0) + 1


def _normalise_names(names: tuple[str, ...]) -> tuple[str, ...]:
    requested = tuple(name.strip().lower() for name in names if name.strip()) or ("scalene",)
    if "all" in requested:
        return ("scalene", "cprofile", "pyinstrument", "py-spy")
    return tuple(dict.fromkeys(requested))


def _unavailable_summary(workload: PerformanceWorkload, profiler: str, detail: str) -> RunSummary:
    python_version, platform_name, _ = RunSummary.environment_defaults()
    return RunSummary(
        run_id=f"unavailable-{profiler}-{workload.configuration_fingerprint[:12]}",
        workload=workload,
        status=EvidenceStatus.UNAVAILABLE,
        started_at="",
        duration_seconds=None,
        return_code=None,
        git_revision="unavailable",
        git_dirty=None,
        python_version=python_version,
        platform_name=platform_name,
        machine_profile="unavailable",
        source_identity=None,
        metrics=(MetricRecord("profile", None, "run", EvidenceStatus.UNAVAILABLE, detail),),
        artifacts=(
            # A null path makes the missing prerequisite explicit without inventing an artifact.
            ProfileArtifact(
                profiler,
                "unknown",
                None,
                None,
                None,
                EvidenceStatus.UNAVAILABLE,
                detail=detail,
            ),
        ),
        diagnostics=(detail,),
    )


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = [
    "PerformanceProfiler",
    "parse_allocation_metrics",
    "parse_method_summaries",
    "parse_pyperf_metrics",
]

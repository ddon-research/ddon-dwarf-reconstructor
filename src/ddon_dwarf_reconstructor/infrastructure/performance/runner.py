"""Isolated process runner for bounded CPU, memory, and I/O evidence."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import psutil

from ...domain.models.performance import (
    EvidenceStatus,
    MetricRecord,
    PerformanceWorkload,
    ProfileArtifact,
    RunSummary,
)
from ..artifacts import SourceIdentityCatalog
from ..logging import get_logger, log_event
from .paths import atomic_write_text, git_metadata, machine_profile, sha256_file

logger = get_logger(__name__)
MAX_CAPTURE_BYTES = 1024 * 1024


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
class ProcessExecution:
    """Captured process result before it is converted into a run summary."""

    samples: tuple[ProcessSnapshot, ...]
    timed_out: bool
    diagnostics: tuple[str, ...]
    return_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    elapsed_seconds: float


class _BoundedCapture:
    """Read a child stream concurrently while retaining only a bounded prefix."""

    def __init__(self, stream) -> None:
        self._stream = stream
        self._chunks: list[str] = []
        self._size = 0
        self.truncated = False

    def read(self) -> None:
        while True:
            chunk = self._stream.read(8192)
            if not chunk:
                return
            remaining = MAX_CAPTURE_BYTES - self._size
            if remaining > 0:
                self._chunks.append(chunk[:remaining])
                self._size += min(len(chunk), remaining)
            if len(chunk) > remaining:
                self.truncated = True

    def text(self) -> str:
        value = "".join(self._chunks)
        return (
            f"{value}\n[output truncated at {MAX_CAPTURE_BYTES} bytes]\n"
            if self.truncated
            else value
        )


class PerformanceRunner:
    """Run one workload in a child process and publish its evidence manifest."""

    def __init__(
        self,
        artifact_root: Path,
        *,
        sample_interval_seconds: float = 0.1,
        source_catalog: SourceIdentityCatalog | None = None,
    ) -> None:
        if sample_interval_seconds <= 0:
            raise ValueError("performance sample interval must be positive")
        self.artifact_root = artifact_root
        self.sample_interval_seconds = sample_interval_seconds
        self.source_catalog = source_catalog or SourceIdentityCatalog()

    def run(
        self,
        workload: PerformanceWorkload,
        *,
        command_factory: Callable[[Path], tuple[str, ...]] | None = None,
        profiler_name: str = "process-sampler",
        profile_format: str = "none",
        profile_filename: str | None = None,
        tool_version: str = "built-in",
    ) -> RunSummary:
        """Execute a workload, sample its process tree, and publish a manifest."""
        if not workload.cwd.is_dir():
            raise ValueError(f"performance workload cwd is not a directory: {workload.cwd}")
        run_id = uuid4().hex
        run_dir = self.artifact_root / workload.name / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        stdout_path = run_dir / "stdout.txt"
        stderr_path = run_dir / "stderr.txt"
        samples_path = run_dir / "process-samples.jsonl"
        profile_path = run_dir / profile_filename if profile_filename else None
        started_at = datetime.now(UTC).isoformat()
        if command_factory is None:
            command = list(workload.command)
        else:
            if profile_path is None:
                raise ValueError("a profile filename is required for a command factory")
            command = list(command_factory(profile_path))
        environment = os.environ.copy()
        environment.update(workload.environment_dict())
        execution = self._execute(command, workload, environment)
        self._write_raw_outputs(
            stdout_path,
            stderr_path,
            samples_path,
            execution,
        )
        metrics = _metrics(
            execution.samples,
            execution.elapsed_seconds,
            execution.timed_out,
            execution.stdout_truncated,
            execution.stderr_truncated,
        )
        summary = self._build_summary(
            run_id,
            workload,
            profiler_name,
            profile_format,
            tool_version,
            profile_path,
            run_dir,
            started_at,
            execution,
            metrics,
            samples_path,
            stdout_path,
            stderr_path,
        )
        self.publish(summary)
        log_event(
            logger,
            logging.INFO,
            "performance_run_published",
            run_id=run_id,
            workload=workload.name,
            status=summary.status.value,
            duration_seconds=summary.duration_seconds,
        )
        return summary

    def _build_summary(
        self,
        run_id: str,
        workload: PerformanceWorkload,
        profiler_name: str,
        profile_format: str,
        tool_version: str,
        profile_path: Path | None,
        run_dir: Path,
        started_at: str,
        execution: ProcessExecution,
        metrics: list[MetricRecord],
        samples_path: Path,
        stdout_path: Path,
        stderr_path: Path,
    ) -> RunSummary:
        artifacts = [_file_artifact("process-sampler", "jsonl", samples_path, "built-in")]
        if profile_path is not None:
            artifacts.append(
                _profile_artifact(profiler_name, profile_format, profile_path, tool_version)
            )
        diagnostics = list(execution.diagnostics)
        source_identity = self._source_identity(workload.source_path, diagnostics)
        revision, dirty = git_metadata(workload.cwd)
        status = _execution_status(execution)
        python_version, platform_name, _ = RunSummary.environment_defaults()
        return RunSummary(
            run_id=run_id,
            workload=workload,
            status=status,
            started_at=started_at,
            duration_seconds=_duration(metrics),
            return_code=execution.return_code,
            git_revision=revision,
            git_dirty=dirty,
            python_version=python_version,
            platform_name=platform_name,
            machine_profile=machine_profile(),
            source_identity=source_identity,
            profiler_mode=profiler_name,
            metrics=tuple(metrics),
            artifacts=tuple(artifacts),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=run_dir / "manifest.json",
            diagnostics=tuple(diagnostics),
        )

    def _execute(
        self,
        command: list[str],
        workload: PerformanceWorkload,
        environment: dict[str, str],
    ) -> ProcessExecution:
        started = monotonic()
        process = self._start_process(command, workload.cwd, environment)
        stdout_capture = _BoundedCapture(process.stdout)
        stderr_capture = _BoundedCapture(process.stderr)
        readers = self._start_readers(stdout_capture, stderr_capture)
        samples, timed_out, diagnostics = self._sample_until_exit(process, workload.timeout_seconds)
        return_code = process.poll()
        process.wait()
        for reader in readers:
            reader.join(timeout=2)
        if return_code not in (None, 0) and not timed_out:
            diagnostics.append(f"child exited with code {return_code}")
        return ProcessExecution(
            samples=tuple(samples),
            timed_out=timed_out,
            diagnostics=tuple(diagnostics),
            return_code=return_code,
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            elapsed_seconds=max(0.0, monotonic() - started),
        )

    @staticmethod
    def _write_raw_outputs(
        stdout_path: Path,
        stderr_path: Path,
        samples_path: Path,
        execution: ProcessExecution,
    ) -> None:
        atomic_write_text(stdout_path, execution.stdout)
        atomic_write_text(stderr_path, execution.stderr)
        sample_lines = "".join(
            json.dumps(sample.to_dict(), sort_keys=True) + "\n" for sample in execution.samples
        )
        atomic_write_text(samples_path, sample_lines)

    @staticmethod
    def publish(summary: RunSummary) -> None:
        """Republish a manifest after a parser adds method-level summaries."""
        PerformanceRunner._publish_manifest(summary)

    @staticmethod
    def _start_process(
        command: list[str], cwd: Path, environment: dict[str, str]
    ) -> subprocess.Popen[str]:
        try:
            if sys.platform == "win32":
                return subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            return subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )
        except OSError as error:
            raise RuntimeError(f"could not start performance workload: {command[0]}") from error

    @staticmethod
    def _start_readers(
        stdout_capture: _BoundedCapture, stderr_capture: _BoundedCapture
    ) -> tuple[threading.Thread, threading.Thread]:
        stdout_reader = threading.Thread(target=stdout_capture.read, daemon=True)
        stderr_reader = threading.Thread(target=stderr_capture.read, daemon=True)
        stdout_reader.start()
        stderr_reader.start()
        return stdout_reader, stderr_reader

    def _sample_until_exit(
        self, process: subprocess.Popen[str], timeout_seconds: float
    ) -> tuple[list[ProcessSnapshot], bool, list[str]]:
        samples: list[ProcessSnapshot] = []
        diagnostics: list[str] = []
        started = monotonic()
        timed_out = False
        while process.poll() is None:
            snapshot = _snapshot(process.pid)
            if snapshot is not None:
                samples.append(snapshot)
            if monotonic() - started >= timeout_seconds:
                timed_out = True
                diagnostics.append(f"timeout after {timeout_seconds:.3f} seconds")
                _terminate_process_tree(process.pid)
                break
            sleep(self.sample_interval_seconds)
        final = _snapshot(process.pid)
        if final is not None:
            samples.append(final)
        if not samples:
            diagnostics.append("process metrics were unavailable")
        return samples, timed_out, diagnostics

    def _source_identity(self, source: Path | None, diagnostics: list[str]) -> str | None:
        if source is None:
            return None
        if not source.exists():
            diagnostics.append(f"source identity unavailable: {source}")
            return None
        try:
            return self.source_catalog.identify(source).sha256
        except (OSError, ValueError) as error:
            diagnostics.append(f"source identity unavailable: {error}")
            return None

    @staticmethod
    def _publish_manifest(summary: RunSummary) -> None:
        if summary.manifest_path is None:
            raise ValueError("performance run manifest path is required")
        payload = {"schema_version": "1", "run": summary.to_dict()}
        atomic_write_text(
            summary.manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )


def _snapshot(pid: int) -> ProcessSnapshot | None:
    processes = _process_tree(pid)
    if processes is None:
        return None
    valid_values = _valid_process_values(processes)
    if not valid_values:
        return None
    return _build_snapshot(valid_values)


def _process_tree(pid: int) -> list[psutil.Process] | None:
    try:
        root = psutil.Process(pid)
        return [root, *root.children(recursive=True)]
    except psutil.Error, OSError:
        return None


def _valid_process_values(
    processes: list[psutil.Process],
) -> list[tuple[float, float, int, int, tuple[int, int, int, int] | None]]:
    values = [_process_values(process) for process in processes]
    return [value for value in values if value is not None]


def _build_snapshot(
    values: list[tuple[float, float, int, int, tuple[int, int, int, int] | None]],
) -> ProcessSnapshot:
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


def _process_values(
    process: psutil.Process,
) -> tuple[float, float, int, int, tuple[int, int, int, int] | None] | None:
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


def _terminate_process_tree(pid: int) -> None:
    try:
        root = psutil.Process(pid)
        children = root.children(recursive=True)
    except psutil.Error, OSError:
        return
    for process in [*reversed(children), root]:
        try:
            process.terminate()
        except psutil.Error:
            continue
    _, alive = psutil.wait_procs([*children, root], timeout=2)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            continue


def _execution_status(execution: ProcessExecution) -> EvidenceStatus:
    if execution.timed_out or execution.return_code not in (None, 0):
        return EvidenceStatus.PARTIAL
    return EvidenceStatus.OBSERVED


def _metrics(
    samples: tuple[ProcessSnapshot, ...],
    elapsed_seconds: float,
    timed_out: bool,
    stdout_truncated: bool,
    stderr_truncated: bool,
) -> list[MetricRecord]:
    status = EvidenceStatus.UNAVAILABLE if not samples else _run_status(timed_out)
    first = samples[0] if samples else None
    last = samples[-1] if samples else None
    peak_rss = _peak(samples, "rss_bytes")
    peak_vms = _peak(samples, "vms_bytes")
    return [
        MetricRecord("wall_time_seconds", elapsed_seconds, "seconds", status),
        MetricRecord(
            "cpu_user_seconds", _delta(first, last, "cpu_user_seconds"), "seconds", status
        ),
        MetricRecord(
            "cpu_system_seconds", _delta(first, last, "cpu_system_seconds"), "seconds", status
        ),
        MetricRecord("peak_rss_bytes", peak_rss, "bytes", status),
        MetricRecord("peak_vms_bytes", peak_vms, "bytes", status),
        MetricRecord("read_bytes", _delta(first, last, "read_bytes"), "bytes", status),
        MetricRecord("write_bytes", _delta(first, last, "write_bytes"), "bytes", status),
        MetricRecord("read_count", _delta(first, last, "read_count"), "count", status),
        MetricRecord("write_count", _delta(first, last, "write_count"), "count", status),
        MetricRecord("sample_count", len(samples), "samples", status),
        _capture_metric("stdout_capture", stdout_truncated),
        _capture_metric("stderr_capture", stderr_truncated),
    ]


def _run_status(timed_out: bool) -> EvidenceStatus:
    return EvidenceStatus.PARTIAL if timed_out else EvidenceStatus.OBSERVED


def _peak(samples: tuple[ProcessSnapshot, ...], field: str) -> int | None:
    values = [getattr(sample, field) for sample in samples]
    return max(values) if values else None


def _capture_metric(name: str, truncated: bool) -> MetricRecord:
    return MetricRecord(
        name,
        MAX_CAPTURE_BYTES if truncated else 0,
        "bytes_truncated",
        EvidenceStatus.PARTIAL if truncated else EvidenceStatus.OBSERVED,
    )


def _delta(
    first: ProcessSnapshot | None, last: ProcessSnapshot | None, field: str
) -> float | int | None:
    if first is None or last is None:
        return None
    start = getattr(first, field)
    end = getattr(last, field)
    if start is None or end is None:
        return None
    return max(0, end - start)


def _duration(metrics: list[MetricRecord]) -> float | None:
    for metric in metrics:
        if metric.name == "wall_time_seconds":
            return metric.value if isinstance(metric.value, float) else None
    return None


def _file_artifact(
    profiler: str, file_format: str, path: Path, tool_version: str
) -> ProfileArtifact:
    return ProfileArtifact(
        profiler=profiler,
        format=file_format,
        path=path,
        size=path.stat().st_size if path.exists() else None,
        sha256=sha256_file(path) if path.exists() else None,
        status=EvidenceStatus.OBSERVED if path.exists() else EvidenceStatus.UNAVAILABLE,
        tool_version=tool_version,
    )


def _profile_artifact(
    profiler: str, file_format: str, path: Path, tool_version: str
) -> ProfileArtifact:
    artifact = _file_artifact(profiler, file_format, path, tool_version)
    if artifact.status == EvidenceStatus.UNAVAILABLE:
        return ProfileArtifact(
            profiler=profiler,
            format=file_format,
            path=path,
            size=None,
            sha256=None,
            status=EvidenceStatus.PARTIAL,
            tool_version=tool_version,
            detail="profiler did not publish the expected output",
        )
    return artifact


__all__ = ["MAX_CAPTURE_BYTES", "PerformanceRunner", "ProcessSnapshot"]

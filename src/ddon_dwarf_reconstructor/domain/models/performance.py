"""Typed contracts for opt-in performance evidence."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class EvidenceStatus(StrEnum):
    """Status vocabulary shared by metrics and published artifacts."""

    OBSERVED = "observed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_OBSERVED = "not_observed"
    BLOCKED = "blocked"


class ColdWarmState(StrEnum):
    """Cache state of a measured workload."""

    COLD = "cold"
    WARM = "warm"


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    """Execution runtime identity captured alongside a workload."""

    name: str
    implementation: str
    python_version: str
    gil_enabled: bool | None
    executable: Path | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("name", self.name),
            ("implementation", self.implementation),
            ("python_version", self.python_version),
        ):
            if not value.strip():
                raise ValueError(f"runtime {field_name} must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a stable runtime descriptor."""
        return {
            "name": self.name,
            "implementation": self.implementation,
            "python_version": self.python_version,
            "gil_enabled": self.gil_enabled,
            "executable": None if self.executable is None else str(self.executable),
        }


@dataclass(frozen=True, slots=True)
class PerformanceWorkload:
    """One bounded command invocation to measure in a child process."""

    name: str
    command: tuple[str, ...]
    cwd: Path
    state: ColdWarmState
    timeout_seconds: float = 300.0
    environment: tuple[tuple[str, str], ...] = ()
    source_path: Path | None = None
    configuration: tuple[tuple[str, str], ...] = ()
    runtime: RuntimeDescriptor | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("performance workload name must not be empty")
        if not self.command:
            raise ValueError("performance workload command must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("performance workload timeout must be positive")

    @property
    def configuration_fingerprint(self) -> str:
        """Return the stable fingerprint for command and workload configuration."""
        payload = {
            "command": list(self.command),
            "configuration": list(self.configuration),
            "cwd": str(self.cwd.resolve()),
            "environment": list(self.environment),
            "name": self.name,
            "runtime": None if self.runtime is None else self.runtime.to_dict(),
            "state": self.state.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def environment_dict(self) -> dict[str, str]:
        """Return a child-process environment overlay."""
        return dict(self.environment)

    def to_dict(self) -> dict[str, object]:
        """Return a stable machine-readable workload descriptor."""
        return {
            "name": self.name,
            "command": list(self.command),
            "cwd": str(self.cwd),
            "state": self.state.value,
            "timeout_seconds": self.timeout_seconds,
            "environment": dict(self.environment),
            "source_path": None if self.source_path is None else str(self.source_path),
            "configuration": dict(self.configuration),
            "runtime": None if self.runtime is None else self.runtime.to_dict(),
            "configuration_fingerprint": self.configuration_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """One aggregate measurement with an explicit evidence status."""

    name: str
    value: float | int | None
    unit: str
    status: EvidenceStatus
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("metric name must not be empty")
        if not self.unit.strip():
            raise ValueError("metric unit must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a stable metric record."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class MethodSummary:
    """Normalized top-N method or line attribution from a profiler."""

    profiler: str
    name: str
    file: str | None = None
    line: int | None = None
    total_seconds: float | None = None
    self_seconds: float | None = None
    call_count: int | None = None
    memory_bytes: int | None = None
    cpu_percent: float | None = None
    rank: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return a stable method summary."""
        return {
            "profiler": self.profiler,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "total_seconds": self.total_seconds,
            "self_seconds": self.self_seconds,
            "call_count": self.call_count,
            "memory_bytes": self.memory_bytes,
            "cpu_percent": self.cpu_percent,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class ProfileArtifact:
    """External profiler output referenced by a run manifest."""

    profiler: str
    format: str
    path: Path | None
    size: int | None
    sha256: str | None
    status: EvidenceStatus
    tool_version: str = "unavailable"
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        """Return a stable external artifact descriptor."""
        return {
            "profiler": self.profiler,
            "format": self.format,
            "path": None if self.path is None else str(self.path),
            "size": self.size,
            "sha256": self.sha256,
            "status": self.status.value,
            "tool_version": self.tool_version,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ToolAvailability:
    """Result of probing one optional profiling tool."""

    name: str
    executable: str | None
    version: str
    status: EvidenceStatus
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        """Return a stable tool availability record."""
        return {
            "name": self.name,
            "executable": self.executable,
            "version": self.version,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Complete summary and evidence references for one measured invocation."""

    run_id: str
    workload: PerformanceWorkload
    status: EvidenceStatus
    started_at: str
    duration_seconds: float | None
    return_code: int | None
    git_revision: str
    git_dirty: bool | None
    python_version: str
    platform_name: str
    machine_profile: str
    source_identity: str | None
    runtime_name: str = "host"
    runtime_implementation: str = "CPython"
    gil_enabled: bool | None = None
    profiler_mode: str = "process-sampler"
    metrics: tuple[MetricRecord, ...] = ()
    method_summaries: tuple[MethodSummary, ...] = ()
    artifacts: tuple[ProfileArtifact, ...] = ()
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    manifest_path: Path | None = None
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def environment_defaults(cls) -> tuple[str, str, str]:
        """Return interpreter, platform, and machine values for a new run."""
        return platform.python_version(), platform.platform(), platform.machine()

    def to_dict(self) -> dict[str, object]:
        """Return the complete stable run summary."""
        return {
            "run_id": self.run_id,
            "workload": self.workload.to_dict(),
            "status": self.status.value,
            "started_at": self.started_at,
            "duration_seconds": self.duration_seconds,
            "return_code": self.return_code,
            "git_revision": self.git_revision,
            "git_dirty": self.git_dirty,
            "python_version": self.python_version,
            "platform": self.platform_name,
            "machine_profile": self.machine_profile,
            "source_identity": self.source_identity,
            "runtime_name": self.runtime_name,
            "runtime_implementation": self.runtime_implementation,
            "gil_enabled": self.gil_enabled,
            "profiler_mode": self.profiler_mode,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "method_summaries": [item.to_dict() for item in self.method_summaries],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "stdout_path": None if self.stdout_path is None else str(self.stdout_path),
            "stderr_path": None if self.stderr_path is None else str(self.stderr_path),
            "manifest_path": None if self.manifest_path is None else str(self.manifest_path),
            "diagnostics": list(self.diagnostics),
        }


PerformanceRun = RunSummary


__all__ = [
    "ColdWarmState",
    "EvidenceStatus",
    "MetricRecord",
    "MethodSummary",
    "PerformanceRun",
    "PerformanceWorkload",
    "ProfileArtifact",
    "RuntimeDescriptor",
    "RunSummary",
    "ToolAvailability",
]

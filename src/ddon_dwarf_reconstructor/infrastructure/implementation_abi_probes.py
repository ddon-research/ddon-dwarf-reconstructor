"""Bounded Orbis-clang ABI probe matrix used as independent compiler evidence."""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from ..domain.models.implementation_validation import CompilerEvidence, ValidationStatus
from .implementation_toolchain import collect_object_metadata

_PROBES: tuple[tuple[str, str], ...] = (
    ("integer", 'extern "C" int probe_integer(int a, long b) { return a + (int)b; }\n'),
    ("floating", 'extern "C" double probe_floating(float a, double b) { return a + b; }\n'),
    (
        "aggregate",
        "struct ProbePair { long a; double b; };\n"
        'extern "C" ProbePair probe_aggregate(ProbePair value) { return value; }\n',
    ),
    (
        "this",
        "struct ProbeObject { int member(int value) const noexcept { return value + 1; } };\n",
    ),
    (
        "hidden_sret",
        "struct ProbeLarge { long a; long b; long c; };\n"
        'extern "C" ProbeLarge probe_hidden_sret(long value) { return {value, value, value}; }\n',
    ),
    (
        "variadic",
        'extern "C" int probe_variadic(int count, ...) { return count; }\n',
    ),
    (
        "virtual",
        "struct ProbeVirtual { virtual int value() const; };\n"
        "int ProbeVirtual::value() const { return 2; }\n",
    ),
    ("noexcept", 'extern "C" int probe_noexcept(int value) noexcept { return value; }\n'),
)


def run_abi_probe_matrix(
    compiler: Path | None,
    output_dir: Path,
    *,
    readelf: Path | None = None,
    timeout_seconds: float | None = None,
) -> tuple[CompilerEvidence, ...]:
    """Compile each ABI shape separately and retain status/hash evidence only."""
    if compiler is None:
        return tuple(
            CompilerEvidence(
                status=ValidationStatus.NOT_OBSERVED,
                profile=f"abi:{_name}",
                diagnostics=("Orbis clang++ was not supplied",),
            )
            for _name, _source in _PROBES
        )
    if not compiler.exists():
        return tuple(
            CompilerEvidence(
                status=ValidationStatus.UNAVAILABLE,
                profile=f"abi:{_name}",
                tool=str(compiler),
                diagnostics=("Orbis clang++ path does not exist",),
            )
            for _name, _source in _PROBES
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    return tuple(
        _run_probe(
            name,
            source,
            compiler,
            output_dir,
            readelf,
            timeout_seconds=timeout_seconds,
        )
        for name, source in _PROBES
    )


def aggregate_probe_status(results: tuple[CompilerEvidence, ...]) -> ValidationStatus:
    """Collapse probe outcomes without hiding an individual failure."""
    if not results:
        return ValidationStatus.NOT_OBSERVED
    statuses = {item.status for item in results}
    if statuses == {ValidationStatus.OBSERVED}:
        return ValidationStatus.OBSERVED
    if ValidationStatus.FAILED in statuses:
        return ValidationStatus.FAILED
    if ValidationStatus.BLOCKED in statuses:
        return ValidationStatus.BLOCKED
    if ValidationStatus.UNAVAILABLE in statuses:
        return ValidationStatus.UNAVAILABLE
    return ValidationStatus.PARTIAL


def _run_probe(
    name: str,
    source: str,
    compiler: Path,
    output_dir: Path,
    readelf: Path | None,
    *,
    timeout_seconds: float | None,
) -> CompilerEvidence:
    source_path = output_dir / f"{name}.cpp"
    object_path = output_dir / f"{name}.o"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = (
        str(compiler),
        "-target",
        "x86_64-scei-ps4",
        "-ffreestanding",
        "-fno-exceptions",
        "-fno-rtti",
        "-O0",
        "-c",
        str(source_path),
        "-o",
        str(object_path),
    )
    tool_hash = _sha256_file(compiler)
    version = _tool_version(compiler, timeout_seconds)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CompilerEvidence(
            status=ValidationStatus.BLOCKED,
            profile=f"abi:{name}",
            tool=str(compiler),
            tool_sha256=tool_hash,
            version=version,
            command=command,
            object_metadata={
                "timeout": _timeout_metadata(str(compiler), f"abi:{name}", started, timeout_seconds)
            },
            diagnostics=(f"ABI probe {name} timed out",),
        )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status = ValidationStatus.OBSERVED if completed.returncode == 0 else ValidationStatus.FAILED
    diagnostics = () if status is ValidationStatus.OBSERVED else (f"ABI probe {name} was rejected",)
    return CompilerEvidence(
        status=status,
        profile=f"abi:{name}",
        tool=str(compiler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        output_path=str(object_path) if object_path.exists() else None,
        output_sha256=_sha256_file(object_path) if object_path.exists() else None,
        object_metadata={
            "stdout_sha256": _sha256_text(stdout),
            "stderr_sha256": _sha256_text(stderr),
            **collect_object_metadata(
                object_path,
                readelf,
                output_dir,
                name,
                timeout_seconds=timeout_seconds,
            ),
        },
        diagnostics=diagnostics,
    )


def _tool_version(path: Path, timeout_seconds: float | None = None) -> str | None:
    try:
        completed = subprocess.run(
            (str(path), "--version"),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0][:512] if output else None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timeout_metadata(
    tool: str, stage: str, started: float, timeout_seconds: float | None
) -> dict[str, object]:
    return {
        "tool": tool,
        "stage": stage,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "configured_limit_seconds": timeout_seconds,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["aggregate_probe_status", "run_abi_probe_matrix"]

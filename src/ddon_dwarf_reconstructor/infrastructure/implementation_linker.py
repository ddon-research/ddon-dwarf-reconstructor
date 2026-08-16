"""Bounded Orbis linker evidence for accepted target objects."""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from ..domain.models.implementation_validation import ValidationStatus


def link_object(
    object_path: Path,
    linker: Path | None,
    output_dir: Path,
    stem: str,
    assembler_status: ValidationStatus,
    *,
    timeout_seconds: float | None = None,
) -> tuple[dict[str, object], Path | None, tuple[str, ...]]:
    """Optionally create and record a relocatable target object."""
    preflight = _link_preflight(linker, assembler_status)
    if preflight is not None:
        return preflight
    assert linker is not None
    linked_path = output_dir / f"{stem}.linked.o"
    command = (str(linker), "-r", "-o", str(linked_path), str(object_path))
    metadata: dict[str, object] = {
        "link_tool": str(linker),
        "link_tool_sha256": _sha256_file(linker),
        "link_version": _tool_version(linker, timeout_seconds),
        "link_command": command,
    }
    return _run_linker(command, linker, linked_path, metadata, timeout_seconds)


def _link_preflight(
    linker: Path | None, assembler_status: ValidationStatus
) -> tuple[dict[str, object], Path | None, tuple[str, ...]] | None:
    if linker is None or assembler_status is not ValidationStatus.OBSERVED:
        diagnostic = (
            "Orbis linker was not run because assembly was not accepted"
            if linker is not None
            else None
        )
        return (
            {"link_status": ValidationStatus.NOT_OBSERVED.value},
            None,
            () if diagnostic is None else (diagnostic,),
        )
    if not linker.exists():
        return (
            {"link_status": ValidationStatus.UNAVAILABLE.value, "link_tool": str(linker)},
            None,
            ("Orbis linker path does not exist",),
        )
    return None


def _run_linker(
    command: tuple[str, ...],
    linker: Path,
    linked_path: Path,
    metadata: dict[str, object],
    timeout_seconds: float | None,
) -> tuple[dict[str, object], Path | None, tuple[str, ...]]:
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
        metadata.update(
            {
                "link_status": ValidationStatus.BLOCKED.value,
                "timeout": _timeout_metadata(str(linker), "linker", started, timeout_seconds),
            }
        )
        return metadata, None, ("Orbis linker timed out",)
    except OSError as error:
        metadata["link_status"] = ValidationStatus.UNAVAILABLE.value
        return metadata, None, (f"Orbis linker could not be executed: {type(error).__name__}",)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status = ValidationStatus.OBSERVED if completed.returncode == 0 else ValidationStatus.FAILED
    metadata.update(
        {
            "link_status": status.value,
            "link_stdout_sha256": _sha256_text(stdout),
            "link_stderr_sha256": _sha256_text(stderr),
            "link_output_sha256": _sha256_file(linked_path) if linked_path.exists() else None,
        }
    )
    diagnostics = (
        () if status is ValidationStatus.OBSERVED else ("Orbis linker rejected the target object",)
    )
    return metadata, linked_path if linked_path.exists() else None, diagnostics


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


__all__ = ["link_object"]

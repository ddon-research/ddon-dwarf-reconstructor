"""Bounded Orbis linker evidence for accepted target objects."""

from __future__ import annotations

import tempfile
import time
from os import replace
from pathlib import Path

from ..core.content_hash import sha256_file, sha256_text
from ..domain.models.implementation_validation import ValidationStatus
from .toolchain_process import (
    BoundedCaptureResult,
    ToolchainExportError,
    ToolIdentityCache,
    run_bounded_capture,
)
from .toolchain_process import timeout_metadata as _timeout_metadata


def link_object(
    object_path: Path,
    linker: Path | None,
    output_dir: Path,
    stem: str,
    assembler_status: ValidationStatus,
    *,
    timeout_seconds: float | None = None,
    identity_cache: ToolIdentityCache | None = None,
) -> tuple[dict[str, object], Path | None, tuple[str, ...]]:
    """Optionally create and record a relocatable target object."""
    preflight = _link_preflight(linker, assembler_status)
    if preflight is not None:
        return preflight
    assert linker is not None
    identity = (identity_cache or ToolIdentityCache()).observe(
        linker,
        timeout_seconds,
        profile="linker",
    )
    linked_path = output_dir / f"{stem}.linked.o"
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{stem}.link-", dir=output_dir) as temporary:
        staged_path = Path(temporary) / linked_path.name
        command = (str(linker), "-r", "-o", str(staged_path), str(object_path))
        metadata: dict[str, object] = {
            "link_tool": str(linker),
            "link_tool_sha256": identity.sha256,
            "link_version": identity.version,
            "link_command": command,
        }
        return _run_linker(
            command,
            linker,
            staged_path,
            linked_path,
            metadata,
            timeout_seconds,
        )


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
    staged_path: Path,
    linked_path: Path,
    metadata: dict[str, object],
    timeout_seconds: float | None,
) -> tuple[dict[str, object], Path | None, tuple[str, ...]]:
    completed, capture_diagnostics = _capture_linker_output(
        command,
        linker,
        metadata,
        timeout_seconds,
    )
    if completed is None:
        return metadata, None, capture_diagnostics
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status, status_diagnostics = _link_capture_status(completed)
    metadata.update(
        {
            "link_status": status.value,
            "link_stdout_sha256": sha256_text(stdout),
            "link_stderr_sha256": sha256_text(stderr),
            "link_output_sha256": None,
        }
    )
    if status_diagnostics:
        return metadata, None, status_diagnostics
    if not staged_path.is_file():
        metadata["link_status"] = ValidationStatus.FAILED.value
        return metadata, None, ("Orbis linker produced no output object",)
    try:
        replace(staged_path, linked_path)
    except OSError as error:
        metadata["link_status"] = ValidationStatus.FAILED.value
        return metadata, None, (f"Orbis linked-object publication failed: {type(error).__name__}",)
    metadata["link_output_sha256"] = sha256_file(linked_path)
    return metadata, linked_path, ()


def _capture_linker_output(
    command: tuple[str, ...],
    linker: Path,
    metadata: dict[str, object],
    timeout_seconds: float | None,
) -> tuple[BoundedCaptureResult | None, tuple[str, ...]]:
    started = time.perf_counter()
    try:
        return run_bounded_capture(linker, command[1:], timeout_seconds), ()
    except TimeoutError:
        metadata.update(
            {
                "link_status": ValidationStatus.BLOCKED.value,
                "timeout": _timeout_metadata(str(linker), "linker", started, timeout_seconds),
            }
        )
        return None, ("Orbis linker timed out",)
    except (OSError, ToolchainExportError) as error:
        metadata["link_status"] = ValidationStatus.UNAVAILABLE.value
        return None, (f"Orbis linker could not be executed: {type(error).__name__}",)


def _link_capture_status(
    completed: BoundedCaptureResult,
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if completed.stdout_truncated or completed.stderr_truncated:
        return ValidationStatus.FAILED, ("Orbis linker output exceeded the bounded cap",)
    if completed.returncode != 0:
        return ValidationStatus.FAILED, ("Orbis linker rejected the target object",)
    return ValidationStatus.OBSERVED, ()


__all__ = ["link_object"]

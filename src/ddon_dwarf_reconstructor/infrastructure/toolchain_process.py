"""Bounded subprocess execution for external binary-tool evidence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import BinaryIO

MAX_DIAGNOSTIC_BYTES = 8 * 1024


class ToolchainExportError(RuntimeError):
    """Raised when an external tool cannot produce a complete export."""


@dataclass
class _StreamCapture:
    """Bounded stream-write accounting shared with one drain thread."""

    total_bytes: int = 0
    written_bytes: int = 0
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class BoundedCommandResult:
    """Exit and bounded-output metadata for one external process."""

    returncode: int
    stdout_bytes: int
    stdout_truncated: bool
    stderr_preview: str


def run_bounded_command(
    executable: Path,
    arguments: tuple[str, ...],
    output_path: Path,
    timeout_seconds: float,
    *,
    max_output_bytes: int | None,
    merge_stderr: bool = False,
) -> BoundedCommandResult:
    """Drain process pipes to a file while bounding captured output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = output_path.with_name(f".{output_path.name}.stderr")
    command = [str(executable), *arguments]
    try:
        with output_path.open("wb") as output, stderr_path.open("wb") as stderr_output:
            result = _run_process(
                command,
                executable,
                output,
                stderr_output,
                timeout_seconds,
                max_output_bytes,
                merge_stderr,
            )
        stderr_preview = read_text_prefix(stderr_path)
    except OSError as error:
        raise ToolchainExportError(f"Could not execute external tool: {executable}") from error
    finally:
        stderr_path.unlink(missing_ok=True)
    return BoundedCommandResult(
        returncode=result.returncode,
        stdout_bytes=result.stdout_bytes,
        stdout_truncated=result.stdout_truncated,
        stderr_preview=stderr_preview,
    )


def read_text_prefix(path: Path) -> str:
    """Read a bounded UTF-8 diagnostic prefix."""
    if not path.is_file():
        return ""
    return path.read_bytes()[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", errors="replace").strip()


def _run_process(
    command: list[str],
    executable: Path,
    output: BinaryIO,
    stderr_output: BinaryIO,
    timeout_seconds: float,
    max_output_bytes: int | None,
    merge_stderr: bool,
) -> BoundedCommandResult:
    """Run one process and drain both pipes without retaining output in memory."""
    stderr_target: int = subprocess.STDOUT if merge_stderr else subprocess.PIPE
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_target)
    if process.stdout is None:
        raise ToolchainExportError(f"External tool has no stdout pipe: {executable}")
    stdout_capture = _StreamCapture()
    stdout_thread = Thread(
        target=_copy_stream,
        args=(process.stdout, output, max_output_bytes, stdout_capture),
        daemon=True,
    )
    stderr_capture = _StreamCapture()
    stderr_thread = _start_stderr_thread(process, stderr_output, stderr_capture, merge_stderr)
    if stderr_thread is not None:
        stderr_thread.start()
    stdout_thread.start()
    returncode = _wait_for_process(
        process, stdout_thread, stderr_thread, timeout_seconds, executable
    )
    stdout_thread.join()
    _join_thread(stderr_thread)
    return BoundedCommandResult(
        returncode=returncode,
        stdout_bytes=stdout_capture.total_bytes,
        stdout_truncated=stdout_capture.truncated,
        stderr_preview="",
    )


def _start_stderr_thread(
    process: subprocess.Popen[bytes],
    stderr_output: BinaryIO,
    capture: _StreamCapture,
    merge_stderr: bool,
) -> Thread | None:
    if merge_stderr:
        return None
    if process.stderr is None:
        raise ToolchainExportError("External tool has no stderr pipe")
    return Thread(
        target=_copy_stream,
        args=(process.stderr, stderr_output, MAX_DIAGNOSTIC_BYTES, capture),
        daemon=True,
    )


def _wait_for_process(
    process: subprocess.Popen[bytes],
    stdout_thread: Thread,
    stderr_thread: Thread | None,
    timeout_seconds: float,
    executable: Path,
) -> int:
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.wait()
        stdout_thread.join()
        _join_thread(stderr_thread)
        raise TimeoutError(
            f"External tool timed out after {timeout_seconds:g}s: {executable.name}"
        ) from error


def _join_thread(thread: Thread | None) -> None:
    if thread is not None:
        thread.join()


def _copy_stream(
    stream: BinaryIO,
    destination: BinaryIO,
    limit: int | None,
    capture: _StreamCapture,
) -> None:
    while chunk := stream.read(64 * 1024):
        capture.total_bytes += len(chunk)
        if limit is None:
            destination.write(chunk)
            capture.written_bytes += len(chunk)
            continue
        remaining = limit - capture.written_bytes
        if remaining > 0:
            accepted = chunk[:remaining]
            destination.write(accepted)
            capture.written_bytes += len(accepted)
        if len(chunk) > max(remaining, 0):
            capture.truncated = True

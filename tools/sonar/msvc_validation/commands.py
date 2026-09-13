"""Bounded command execution for compiler evidence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from threading import Thread
from typing import BinaryIO

MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class CommandExecution:
    """Result of one bounded external command."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def run_command(
    arguments: list[str],
    *,
    timeout_seconds: int,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> CommandExecution:
    """Run a command with finite time and bounded retained diagnostics."""
    if max_output_bytes < 1:
        raise ValueError("max_output_bytes must be positive")
    process = subprocess.Popen(
        arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        _terminate(process)
        raise OSError("external command did not provide output pipes")
    stdout_capture = _StreamCapture()
    stderr_capture = _StreamCapture()
    stdout_thread = Thread(
        target=_drain,
        args=(process.stdout, stdout_capture, max_output_bytes),
        daemon=True,
    )
    stderr_thread = Thread(
        target=_drain,
        args=(process.stderr, stderr_capture, max_output_bytes),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
            _terminate(process)
    finally:
        if process.poll() is None:
            _terminate(process)
        stdout_thread.join()
        stderr_thread.join()
    if stdout_capture.error is not None:
        raise OSError("failed to capture external command stdout") from stdout_capture.error
    if stderr_capture.error is not None:
        raise OSError("failed to capture external command stderr") from stderr_capture.error
    return CommandExecution(
        returncode,
        stdout_capture.text,
        stderr_capture.text,
        timed_out=timed_out,
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
    )


@dataclass
class _StreamCapture:
    """Retain a bounded prefix while draining the complete child stream."""

    chunks: list[bytes] = field(default_factory=list)
    retained_bytes: int = 0
    truncated: bool = False
    error: Exception | None = None

    @property
    def text(self) -> str:
        return b"".join(self.chunks).decode(errors="replace")


def _drain(stream: BinaryIO, capture: _StreamCapture, limit: int) -> None:
    try:
        while True:
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                return
            remaining = limit - capture.retained_bytes
            if remaining > 0:
                accepted = chunk[:remaining]
                capture.chunks.append(accepted)
                capture.retained_bytes += len(accepted)
            if len(chunk) > max(remaining, 0):
                capture.truncated = True
    except (OSError, ValueError) as error:
        capture.error = error


def _terminate(process: subprocess.Popen[bytes]) -> None:
    """Terminate a timed-out process and wait for its handle to close."""
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

"""Bounded subprocess execution for external binary-tool evidence."""

from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from typing import BinaryIO

from ..core.content_hash import sha256_file

MAX_DIAGNOSTIC_BYTES = 8 * 1024
MAX_CAPTURE_BYTES = 64 * 1024 * 1024


class ToolchainExportError(RuntimeError):
    """Raised when an external tool cannot produce a complete export."""


@dataclass
class _StreamCapture:
    """Bounded stream-write accounting shared with one drain thread."""

    total_bytes: int = 0
    written_bytes: int = 0
    truncated: bool = False
    error: Exception | None = None


@dataclass(frozen=True, slots=True)
class BoundedCommandResult:
    """Exit and bounded-output metadata for one external process."""

    returncode: int
    stdout_bytes: int
    stdout_truncated: bool
    stderr_preview: str
    stderr_truncated: bool = False


@dataclass(frozen=True, slots=True)
class BoundedCaptureResult:
    """Bounded text output from one external process."""

    returncode: int
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Executable identity observed during one bounded tool invocation scope."""

    executable: Path
    sha256: str | None
    version: str | None


@dataclass(slots=True)
class ToolIdentityCache:
    """Cache tool identity only for the owning run, never process globally."""

    _entries: dict[tuple[Path, float | None, str], ToolIdentity] = field(default_factory=dict)

    def observe(
        self,
        executable: Path,
        timeout_seconds: float | None = None,
        *,
        profile: str = "",
    ) -> ToolIdentity:
        """Return one source-bound executable hash/version observation."""
        resolved = executable.resolve()
        key = (resolved, timeout_seconds, profile)
        cached = self._entries.get(key)
        if cached is not None:
            return cached
        try:
            executable_sha256 = sha256_file(resolved)
        except OSError:
            executable_sha256 = None
        identity = ToolIdentity(
            executable=resolved,
            sha256=executable_sha256,
            version=read_tool_version(resolved, timeout_seconds),
        )
        self._entries[key] = identity
        return identity


def run_bounded_command(
    executable: Path,
    arguments: tuple[str, ...],
    output_path: Path,
    timeout_seconds: float | None,
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
        stderr_truncated=result.stderr_truncated,
    )


def read_tool_version(path: Path, timeout_seconds: float | None = None) -> str | None:
    """Read the first bounded version line from an executable.

    Version output is diagnostic metadata, so a timeout, missing executable,
    or failed capture returns ``None``. A tool may report its version on stderr
    or with a non-zero status, matching the legacy probe behavior. The process
    is still run through the same bounded pipe draining and cleanup path as
    other tool exports.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="ddon-tool-version-") as temporary:
            stdout_path = Path(temporary) / "stdout"
            result = run_bounded_command(
                path,
                ("--version",),
                stdout_path,
                timeout_seconds,
                max_output_bytes=MAX_DIAGNOSTIC_BYTES,
            )
            output = read_text_prefix(stdout_path) or result.stderr_preview
    except OSError, TimeoutError, ToolchainExportError:
        return None
    return output.splitlines()[0][:512] if output else None


def timeout_metadata(
    tool: str, stage: str, started: float, timeout_seconds: float | None
) -> dict[str, object]:
    """Return stable timeout evidence shared by tool adapters."""
    return {
        "tool": tool,
        "stage": stage,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "configured_limit_seconds": timeout_seconds,
    }


def run_bounded_capture(
    executable: Path,
    arguments: tuple[str, ...],
    timeout_seconds: float | None,
    *,
    max_output_bytes: int = MAX_CAPTURE_BYTES,
    max_stderr_bytes: int = MAX_CAPTURE_BYTES,
) -> BoundedCaptureResult:
    """Run a text-producing tool through the bounded process lifecycle."""
    with tempfile.TemporaryDirectory(prefix="ddon-tool-capture-") as temporary:
        root = Path(temporary)
        stdout_path = root / "stdout"
        stderr_path = root / "stderr"
        command = [str(executable), *arguments]
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                result = _run_process(
                    command,
                    executable,
                    stdout,
                    stderr,
                    timeout_seconds,
                    max_output_bytes,
                    False,
                    stderr_limit=max_stderr_bytes,
                )
            return BoundedCaptureResult(
                returncode=result.returncode,
                stdout=stdout_path.read_bytes().decode("utf-8", errors="replace"),
                stderr=stderr_path.read_bytes().decode("utf-8", errors="replace"),
                stdout_truncated=result.stdout_truncated,
                stderr_truncated=result.stderr_truncated,
            )
        except OSError as error:
            raise ToolchainExportError(f"Could not execute external tool: {executable}") from error


def read_text_prefix(path: Path) -> str:
    """Read a bounded UTF-8 diagnostic prefix."""
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        return stream.read(MAX_DIAGNOSTIC_BYTES).decode("utf-8", errors="replace").strip()


def _run_process(
    command: list[str],
    executable: Path,
    output: BinaryIO,
    stderr_output: BinaryIO,
    timeout_seconds: float | None,
    max_output_bytes: int | None,
    merge_stderr: bool,
    *,
    stderr_limit: int = MAX_DIAGNOSTIC_BYTES,
) -> BoundedCommandResult:
    """Run one process and drain both pipes without retaining output in memory."""
    stderr_target: int = subprocess.STDOUT if merge_stderr else subprocess.PIPE
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_target)
    stdout_thread: Thread | None = None
    stderr_thread: Thread | None = None
    try:
        if process.stdout is None:
            raise ToolchainExportError(f"External tool has no stdout pipe: {executable}")
        stdout_capture = _StreamCapture()
        stdout_thread = Thread(
            target=_copy_stream,
            args=(process.stdout, output, max_output_bytes, stdout_capture),
            daemon=True,
        )
        stderr_capture = _StreamCapture()
        stderr_thread = _start_stderr_thread(
            process,
            stderr_output,
            stderr_capture,
            merge_stderr,
            stderr_limit,
        )
        if stderr_thread is not None:
            stderr_thread.start()
        stdout_thread.start()
        returncode = _wait_for_process(
            process, stdout_thread, stderr_thread, timeout_seconds, executable
        )
        stdout_thread.join()
        _join_thread(stderr_thread)
        _raise_stream_error(stdout_capture, "stdout", executable)
        _raise_stream_error(stderr_capture, "stderr", executable)
        return BoundedCommandResult(
            returncode=returncode,
            stdout_bytes=stdout_capture.total_bytes,
            stdout_truncated=stdout_capture.truncated,
            stderr_preview="",
            stderr_truncated=stderr_capture.truncated,
        )
    except BaseException:
        _terminate_process(process)
        _join_thread(stdout_thread)
        _join_thread(stderr_thread)
        raise


def _start_stderr_thread(
    process: subprocess.Popen[bytes],
    stderr_output: BinaryIO,
    capture: _StreamCapture,
    merge_stderr: bool,
    limit: int,
) -> Thread | None:
    if merge_stderr:
        return None
    if process.stderr is None:
        raise ToolchainExportError("External tool has no stderr pipe")
    return Thread(
        target=_copy_stream,
        args=(process.stderr, stderr_output, limit, capture),
        daemon=True,
    )


def _wait_for_process(
    process: subprocess.Popen[bytes],
    stdout_thread: Thread,
    stderr_thread: Thread | None,
    timeout_seconds: float | None,
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


def _raise_stream_error(capture: _StreamCapture, stream_name: str, executable: Path) -> None:
    if capture.error is not None:
        raise ToolchainExportError(
            f"External tool {stream_name} capture failed: {executable}"
        ) from capture.error


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Best-effort cleanup for setup, drain, and timeout failures."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=0.5)
    except OSError, subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait()
        except OSError:
            return


def _copy_stream(
    stream: BinaryIO,
    destination: BinaryIO,
    limit: int | None,
    capture: _StreamCapture,
) -> None:
    try:
        while chunk := stream.read(64 * 1024):
            capture.total_bytes += len(chunk)
            if capture.error is not None:
                continue
            try:
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
            except Exception as error:
                # Keep draining the pipe so a child cannot deadlock behind a
                # failed diagnostic destination; the caller receives the error
                # after the process and both drain threads have been joined.
                capture.error = error
    except Exception as error:
        capture.error = error

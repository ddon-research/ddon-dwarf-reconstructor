"""Bounded diagnostic reads must not load complete tool output files."""

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure import toolchain_process
from ddon_dwarf_reconstructor.infrastructure.toolchain_process import (
    MAX_DIAGNOSTIC_BYTES,
    ToolchainExportError,
    ToolIdentityCache,
    _copy_stream,
    _run_process,
    _StreamCapture,
    read_text_prefix,
    run_bounded_capture,
)

pytestmark = [pytest.mark.unit, pytest.mark.non_functional]


def test_diagnostic_prefix_bounds_the_file_read() -> None:
    reads: list[int] = []

    class BoundedStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            reads.append(size)
            assert 0 <= size <= MAX_DIAGNOSTIC_BYTES
            return super().read(size)

    path = Mock(spec=Path)
    path.is_file.return_value = True
    path.open.return_value = BoundedStream(b"x" * (MAX_DIAGNOSTIC_BYTES + 100))

    assert read_text_prefix(path) == "x" * MAX_DIAGNOSTIC_BYTES
    assert reads == [MAX_DIAGNOSTIC_BYTES]


def test_diagnostic_prefix_preserves_decoding_and_missing_file_behavior(tmp_path: Path) -> None:
    path = tmp_path / "diagnostic.txt"
    assert read_text_prefix(path) == ""
    path.write_bytes(b"  failed\xff \n")
    assert read_text_prefix(path) == "failed\ufffd"


def test_bounded_capture_preserves_text_status_and_truncation() -> None:
    result = run_bounded_capture(
        Path(sys.executable),
        ("-c", "import sys; sys.stdout.write('stdout'); sys.stderr.write('stderr')"),
        5,
        max_output_bytes=4,
        max_stderr_bytes=4,
    )

    assert result.returncode == 0
    assert result.stdout == "stdo"
    assert result.stderr == "stde"
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True


def test_tool_identity_cache_is_run_scoped_and_profile_sensitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "tool"
    executable.write_bytes(b"tool")
    versions: list[tuple[Path, float | None]] = []

    def version(path: Path, timeout_seconds: float | None = None) -> str:
        versions.append((path, timeout_seconds))
        return "tool 1.0"

    monkeypatch.setattr(toolchain_process, "read_tool_version", version)
    cache = ToolIdentityCache()
    first = cache.observe(executable, 2, profile="assembler")
    assert cache.observe(executable, 2, profile="assembler") is first
    assert cache.observe(executable, 2, profile="linker").version == "tool 1.0"
    assert len(versions) == 2
    assert ToolIdentityCache().observe(executable, 2, profile="assembler").version == "tool 1.0"
    assert len(versions) == 3


def test_stream_writer_failures_are_retained_while_the_pipe_is_drained() -> None:
    class FailingDestination:
        def write(self, _value: bytes) -> None:
            raise OSError("destination closed")

    capture = _StreamCapture()
    _copy_stream(BytesIO(b"x" * (MAX_DIAGNOSTIC_BYTES + 1)), FailingDestination(), None, capture)

    assert isinstance(capture.error, OSError)
    assert capture.total_bytes == MAX_DIAGNOSTIC_BYTES + 1
    assert capture.written_bytes == 0


class _FakeProcess:
    def __init__(self, *, stdout: BytesIO | None = None, stderr: BytesIO | None = None) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self.returncode = 0
        return 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def test_run_process_promotes_drain_failure_to_bounded_tool_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stdout=BytesIO(b"output"), stderr=BytesIO(b""))
    monkeypatch.setattr(
        "ddon_dwarf_reconstructor.infrastructure.toolchain_process.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )

    class FailingDestination:
        def write(self, _value: bytes) -> None:
            raise OSError("write failed")

    with pytest.raises(ToolchainExportError, match="stdout capture failed") as raised:
        _run_process(["tool"], Path("tool"), FailingDestination(), BytesIO(), 1, None, False)

    assert isinstance(raised.value.__cause__, OSError)


def test_run_process_terminates_process_without_stdout_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stdout=None)
    monkeypatch.setattr(
        "ddon_dwarf_reconstructor.infrastructure.toolchain_process.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )

    with pytest.raises(ToolchainExportError, match="no stdout pipe"):
        _run_process(["tool"], Path("tool"), BytesIO(), BytesIO(), 1, None, False)

    assert process.terminated is True

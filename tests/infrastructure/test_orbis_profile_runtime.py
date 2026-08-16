"""Tests for concise, explicitly configured Orbis tool diagnostics."""

from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock

import pytest

import ddon_dwarf_reconstructor.infrastructure.orbis_objdump as orbis
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import (
    DEFAULT_TIMEOUT_SECONDS,
    OrbisObjdumpProducer,
)


@pytest.mark.unit
def test_orbis_command_and_metadata_errors_are_specific() -> None:
    producer = OrbisObjdumpProducer.__new__(OrbisObjdumpProducer)
    producer._run = Mock(return_value="")
    with pytest.raises(ValueError, match="no version"):
        producer._read_version()

    producer._run = Mock(return_value="unexpected output")
    with pytest.raises(ValueError, match="did not report"):
        producer._read_target(Path("fixture.elf"))

    producer.executable = Path("objdump")
    producer.timeout_seconds = 1.0
    producer.__dict__.pop("_run")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            orbis.subprocess,
            "run",
            Mock(
                side_effect=TimeoutExpired(
                    ["objdump"], 1.0, output=b"partial stdout", stderr=b"partial stderr"
                )
            ),
        )
        with pytest.raises(TimeoutError, match="timed out"):
            producer._run([])
        assert producer._last_capture == ("", "", -1)

        monkeypatch.setattr(
            orbis.subprocess,
            "run",
            Mock(return_value=CompletedProcess(["objdump"], 2, stdout="", stderr="failed")),
        )
        with pytest.raises(RuntimeError, match=r"failed \(2\)"):
            producer._run([])


@pytest.mark.unit
@pytest.mark.functional
def test_profile_timeout_is_explicit_and_does_not_retain_partial_text() -> None:
    producer = OrbisObjdumpProducer.__new__(OrbisObjdumpProducer)
    producer.executable = Path("objdump")
    producer.timeout_seconds = 7.0
    producer._last_capture = None

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            orbis.subprocess,
            "run",
            Mock(side_effect=TimeoutExpired(["objdump"], 7.0, output=b"partial")),
        )
        result = producer._execute_profile(producer.executable, ["--help"])

    assert DEFAULT_TIMEOUT_SECONDS is None
    assert result.status == "timeout"
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.diagnostics == ("profile timed out (limit=7s)",)

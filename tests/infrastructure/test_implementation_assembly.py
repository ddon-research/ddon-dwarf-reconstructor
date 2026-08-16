"""Focused tests for canonical assembly and SDK object emission."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction
from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure import implementation_toolchain


@pytest.mark.unit
@pytest.mark.functional
def test_canonical_assembly_source_and_sdk_assembler_acceptance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    invalid_source, invalid_diagnostics = implementation_toolchain.canonical_assembly_source(
        "invalid", (OrbisInstruction(0, "zz", "nop", ""),)
    )
    assert invalid_source is None
    assert invalid_diagnostics == ("non-hex raw bytes at 0x0",)

    source, diagnostics = implementation_toolchain.canonical_assembly_source(
        "valid method", (OrbisInstruction(0, "90", "nop", ""),)
    )
    assert diagnostics == ()
    assert source is not None and ".byte 0x90" in source
    assert implementation_toolchain.assemble_canonical_source("method", source, None)[0] is None
    missing = implementation_toolchain.assemble_canonical_source(
        "method", source, tmp_path / "missing-orbis-as"
    )
    assert missing[0] is None

    assembler = tmp_path / "orbis-as"
    assembler.write_bytes(b"tool")

    def accept_object(command: tuple[str, ...], **_kwargs: object) -> SimpleNamespace:
        if "-o" in command:
            Path(command[command.index("-o") + 1]).write_bytes(b"accepted-object")
        return SimpleNamespace(returncode=0, stdout="orbis-as 8.0\n", stderr="")

    monkeypatch.setattr(implementation_toolchain.subprocess, "run", accept_object)
    object_bytes, diagnostics = implementation_toolchain.assemble_canonical_source(
        "method", source, assembler
    )
    assert object_bytes == b"accepted-object"
    assert diagnostics == ()

    monkeypatch.setattr(
        implementation_toolchain.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("as", 1)),
    )
    assert implementation_toolchain.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler execution timed out",
    )
    monkeypatch.setattr(
        implementation_toolchain.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cannot execute")),
    )
    assert implementation_toolchain.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler could not be executed",
    )
    monkeypatch.setattr(
        implementation_toolchain.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="rejected"),
    )
    assert implementation_toolchain.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler rejected canonical assembly",
    )
    monkeypatch.setattr(implementation_toolchain.subprocess, "run", accept_object)
    compiler, parity, artifacts = implementation_toolchain.emit_and_assemble_method(
        "accepted",
        (OrbisInstruction(0, "90", "nop", ""),),
        tmp_path / "accepted",
        assembler,
        effect_status=ValidationStatus.OBSERVED,
    )
    assert compiler.status is ValidationStatus.OBSERVED
    assert parity.status is ValidationStatus.PARTIAL
    assert any(path.endswith(".o") for path in artifacts)
    compiler, _parity, artifacts = implementation_toolchain.emit_and_assemble_method(
        "empty", (), tmp_path / "empty", assembler, effect_status=ValidationStatus.OBSERVED
    )
    assert compiler.status is ValidationStatus.NOT_OBSERVED
    assert artifacts == ()

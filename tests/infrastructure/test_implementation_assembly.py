"""Focused tests for canonical assembly and SDK object emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    CompilerEvidence,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure import (
    implementation_assembler,
    implementation_toolchain,
)
from ddon_dwarf_reconstructor.infrastructure.toolchain_process import BoundedCaptureResult


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

    def accept_object(
        _executable: Path, command: tuple[str, ...], _timeout: float | None, **_kwargs: object
    ) -> BoundedCaptureResult:
        if "-o" in command:
            Path(command[command.index("-o") + 1]).write_bytes(b"accepted-object")
        return BoundedCaptureResult(0, "orbis-as 8.0\n", "", False, False)

    monkeypatch.setattr(implementation_assembler, "run_bounded_capture", accept_object)
    monkeypatch.setattr(implementation_toolchain, "run_bounded_capture", accept_object)
    object_bytes, diagnostics = implementation_toolchain.assemble_canonical_source(
        "method", source, assembler
    )
    assert object_bytes == b"accepted-object"
    assert diagnostics == ()

    monkeypatch.setattr(implementation_assembler, "run_bounded_capture", accept_object)
    monkeypatch.setattr(implementation_toolchain, "run_bounded_capture", accept_object)
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


@pytest.mark.unit
@pytest.mark.functional
def test_canonical_assembler_failure_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, diagnostics = implementation_toolchain.canonical_assembly_source(
        "valid method", (OrbisInstruction(0, "90", "nop", ""),)
    )
    assert diagnostics == ()
    assert source is not None
    assembler = tmp_path / "orbis-as"
    assembler.write_bytes(b"tool")

    monkeypatch.setattr(
        implementation_assembler,
        "run_bounded_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("as")),
    )
    assert implementation_assembler.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler execution timed out",
    )
    monkeypatch.setattr(
        implementation_assembler,
        "run_bounded_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cannot execute")),
    )
    assert implementation_assembler.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler could not be executed",
    )
    monkeypatch.setattr(
        implementation_assembler,
        "run_bounded_capture",
        lambda *_args, **_kwargs: BoundedCaptureResult(1, "", "rejected", False, False),
    )
    assert implementation_assembler.assemble_canonical_source("method", source, assembler)[1] == (
        "Orbis assembler rejected canonical assembly",
    )


@pytest.mark.unit
@pytest.mark.functional
def test_sectioned_assembly_is_opt_in_and_checks_the_orbis_flag() -> None:
    instructions = (OrbisInstruction(0, "90", "nop", ""),)
    default, default_diagnostics = implementation_toolchain.canonical_assembly_source(
        "sectioned method", instructions
    )
    sectioned, sectioned_diagnostics = implementation_toolchain.canonical_assembly_source(
        "sectioned method", instructions, assembly_profile="sectioned"
    )
    assert default_diagnostics == ()
    assert sectioned_diagnostics == ()
    assert default is not None and ".text\n" in default
    assert sectioned is not None
    assert '.section .text.sectioned_method,"ax",@progbits' in sectioned
    assert ".function_and_data_sections" in sectioned
    assert ".function_and_data_sections" not in default

    observed = CompilerEvidence(
        status=ValidationStatus.OBSERVED,
        object_metadata={
            "function_data_sections_enabled": True,
            "text_subsections": (".text.sectioned_method",),
        },
    )
    status, diagnostics = implementation_toolchain._validate_assembly_profile(
        observed, "sectioned_method", "sectioned"
    )
    assert status is ValidationStatus.OBSERVED
    assert diagnostics == ()

    invalid = observed.__class__(
        status=ValidationStatus.OBSERVED,
        object_metadata={"function_data_sections_enabled": False, "text_subsections": ()},
    )
    status, diagnostics = implementation_toolchain._validate_assembly_profile(
        invalid, "sectioned_method", "sectioned"
    )
    assert status is ValidationStatus.FAILED
    assert any("EF_FFUNC_DATA_SECS_ENABLED" in item for item in diagnostics)


@pytest.mark.unit
@pytest.mark.regression
def test_canonical_assembly_requires_complete_contiguous_instruction_bytes() -> None:
    discontinuous, discontinuous_diagnostics = implementation_toolchain.canonical_assembly_source(
        "gap",
        (
            OrbisInstruction(0x1000, "90", "nop", ""),
            OrbisInstruction(0x1002, "c3", "ret", ""),
        ),
    )
    incomplete, incomplete_diagnostics = implementation_toolchain.canonical_assembly_source(
        "truncated",
        (OrbisInstruction(0x1000, "90", "nop", ""),),
        expected_start=0x1000,
        expected_size=2,
    )

    assert discontinuous is None
    assert discontinuous_diagnostics == (
        "instruction at 0x1002 is not contiguous; expected 0x1001",
    )
    assert incomplete is None
    assert incomplete_diagnostics == ("instruction bytes cover 1 byte(s); expected 2",)

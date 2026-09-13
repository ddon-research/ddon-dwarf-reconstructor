"""Tests for the bounded, marker-gated llvm-mca workflow."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import EvidenceStatus
from ddon_dwarf_reconstructor.infrastructure.performance import llvm_mca
from ddon_dwarf_reconstructor.infrastructure.toolchain_process import BoundedCommandResult


@pytest.mark.unit
@pytest.mark.functional
def test_llvm_mca_requires_closed_unique_regions(tmp_path: Path) -> None:
    tool = Path(sys.executable)
    assembly = tmp_path / "unmarked.s"
    assembly.write_text("nop\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one"):
        llvm_mca.analyze_assembly(assembly, tool, tmp_path / "out")

    assembly.write_text(
        "# LLVM-MCA-BEGIN hot\nnop\n# LLVM-MCA-BEGIN nested\nnop\n# LLVM-MCA-END\n# LLVM-MCA-END\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="may not overlap"):
        llvm_mca.analyze_assembly(assembly, tool, tmp_path / "out")


@pytest.mark.unit
@pytest.mark.functional
def test_llvm_mca_publishes_input_tool_output_and_marker_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assembly = tmp_path / "marked.s"
    assembly.write_text(
        "# LLVM-MCA-BEGIN hot\nnop\n# LLVM-MCA-END\n",
        encoding="utf-8",
    )
    tool = Path(sys.executable)

    def bounded(
        _tool: Path,
        _arguments: tuple[str, ...],
        output: Path,
        _timeout: float,
        *,
        max_output_bytes: int,
    ) -> BoundedCommandResult:
        assert max_output_bytes > 0
        output.write_text("llvm-mca result\n", encoding="utf-8")
        return BoundedCommandResult(0, 18, False, "")

    monkeypatch.setattr(llvm_mca, "run_bounded_command", bounded)
    monkeypatch.setattr(llvm_mca, "_tool_version", lambda *_args: "llvm-mca test")
    evidence = llvm_mca.analyze_assembly(assembly, tool, tmp_path / "out")
    assert evidence.status is EvidenceStatus.OBSERVED
    assert evidence.regions == ("hot",)
    assert evidence.output_path is not None and evidence.output_path.is_file()
    assert evidence.manifest_path is not None and evidence.manifest_path.is_file()
    assert evidence.output_sha256
    assert evidence.to_dict()["input_sha256"] == evidence.input_sha256


@pytest.mark.unit
@pytest.mark.functional
def test_llvm_mca_truncation_remains_failed_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assembly = tmp_path / "marked.s"
    assembly.write_text(
        "# LLVM-MCA-BEGIN hot\nnop\n# LLVM-MCA-END\n",
        encoding="utf-8",
    )
    tool = Path(sys.executable)

    monkeypatch.setattr(
        llvm_mca,
        "run_bounded_command",
        lambda *_args, **_kwargs: BoundedCommandResult(0, 1, True, ""),
    )
    monkeypatch.setattr(llvm_mca, "_tool_version", lambda *_args: "llvm-mca test")
    evidence = llvm_mca.analyze_assembly(assembly, tool, tmp_path / "out")
    assert evidence.status is EvidenceStatus.FAILED
    assert "bounded cap" in evidence.diagnostics[0]

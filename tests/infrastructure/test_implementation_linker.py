"""Linker artifact freshness and failure ownership tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure import implementation_linker
from ddon_dwarf_reconstructor.infrastructure.toolchain_process import BoundedCaptureResult

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_linker_failure_does_not_reuse_or_destroy_previous_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "objects"
    output_dir.mkdir()
    object_path = output_dir / "method.o"
    object_path.write_bytes(b"object")
    linker = tmp_path / "orbis-ld"
    linker.write_bytes(b"tool")
    previous = output_dir / "method.linked.o"
    previous.write_bytes(b"previous-valid-link")

    monkeypatch.setattr(
        implementation_linker,
        "run_bounded_capture",
        lambda *_args, **_kwargs: BoundedCaptureResult(1, "", "bad", False, False),
    )

    metadata, linked_path, diagnostics = implementation_linker.link_object(
        object_path, linker, output_dir, "method", ValidationStatus.OBSERVED
    )

    assert metadata["link_status"] == ValidationStatus.FAILED.value
    assert metadata["link_output_sha256"] is None
    assert linked_path is None
    assert diagnostics
    assert previous.read_bytes() == b"previous-valid-link"
    assert not tuple(output_dir.glob(".*.link-*"))


def test_linker_success_without_an_output_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "objects"
    output_dir.mkdir()
    object_path = output_dir / "method.o"
    object_path.write_bytes(b"object")
    linker = tmp_path / "orbis-ld"
    linker.write_bytes(b"tool")

    monkeypatch.setattr(
        implementation_linker,
        "run_bounded_capture",
        lambda *_args, **_kwargs: BoundedCaptureResult(0, "", "", False, False),
    )

    metadata, linked_path, diagnostics = implementation_linker.link_object(
        object_path, linker, output_dir, "method", ValidationStatus.OBSERVED
    )

    assert metadata["link_status"] == ValidationStatus.FAILED.value
    assert linked_path is None
    assert diagnostics == ("Orbis linker produced no output object",)
    assert not (output_dir / "method.linked.o").exists()

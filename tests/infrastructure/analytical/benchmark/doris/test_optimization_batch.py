"""Tests for the combined positive Doris optimization batch."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.optimization as module
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_combined_candidate_provisions_mutually_exclusive_name_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def provision(
        elf: Path,
        manifest_path: Path,
        config: DorisConfig,
        candidate: object,
    ) -> dict[str, object]:
        del elf, manifest_path, config
        candidate_id = str(candidate.candidate_id)
        calls.append(candidate_id)
        return {"candidate_id": candidate_id, "status": "observed"}

    monkeypatch.setattr(module, "_provision_candidate", provision)
    monkeypatch.setattr(
        module,
        "load_manifest",
        lambda path: SimpleNamespace(source_identity=SimpleNamespace(sha256="source-sha")),
    )

    result = module._provision_combined_candidate(
        Path("source.elf"), Path("manifest.json"), DorisConfig()
    )

    assert calls == ["name-lookup-b2", "name-lookup-b4", "name-lookup-b8"]
    assert result["active_lookup_candidate"] == "name-lookup-b8"
    assert result["source_id"] == "source-sha"
    assert [item["candidate_id"] for item in result["components"]] == calls

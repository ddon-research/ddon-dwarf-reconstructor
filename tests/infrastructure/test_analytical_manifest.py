"""Manifest identity contracts for the analytical DWARF store."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import MaterializationManifest

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_manifest_rejects_invalid_source_identity() -> None:
    payload = {
        "schema_version": "1.0",
        "source_path": "sample.elf",
        "source_identity": {
            "sha256": "a",
            "size": 1,
            "mtime_ns": 1,
            "ctime_ns": 1,
            "device": 1,
            "inode": 1,
        },
        "producer": "test",
        "platform": "unknown",
        "files": {},
        "counts": {},
    }
    manifest = MaterializationManifest.from_dict(payload)
    assert manifest.source_identity.sha256 == "a"

"""Serialization and content-hash helpers keep separate ownership boundaries."""

from __future__ import annotations

import pytest

import ddon_dwarf_reconstructor.core.content_hash as content_hash
import ddon_dwarf_reconstructor.core.serialization as serialization

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_content_hash_owns_hash_helpers_without_serialization_forwarders() -> None:
    assert content_hash.sha256_text("evidence") == (
        "ee8250fb76e094b34b471f13a73dbbe51d1ae142e9df59d7c0d31ec20f0a0a8e"
    )
    assert "sha256_text" not in serialization.__all__
    assert not hasattr(serialization, "sha256_text")
    assert not hasattr(serialization, "sha256_bytes")

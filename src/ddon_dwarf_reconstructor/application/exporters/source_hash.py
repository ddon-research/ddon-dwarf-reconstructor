"""Compatibility fallback for direct exporter construction."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ...domain.ports.source_identity import SourceHashPort


class StreamingSourceHash:
    """Hash a source directly when no durable infrastructure adapter is wired."""

    def sha256(self, source_path: Path) -> str:
        digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def __call__(self, source_path: Path) -> str:
        return self.sha256(source_path)


def default_source_hash() -> SourceHashPort:
    """Return the compatibility source-hash implementation."""
    return StreamingSourceHash()

"""Canonical hashes for source-derived content bundles."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path


def header_bundle_sha256(headers: Mapping[str, str]) -> str:
    """Return the canonical digest of sorted header names and UTF-8 contents."""
    digest = hashlib.sha256()
    for filename, content in sorted(headers.items()):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of one bounded metadata or source artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

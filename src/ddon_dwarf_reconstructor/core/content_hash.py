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


def sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 of bounded bytes."""
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    """Return the SHA-256 of UTF-8 text."""
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of one bounded metadata or source artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["header_bundle_sha256", "sha256_bytes", "sha256_file", "sha256_text"]

"""Deterministic output helpers for analytical benchmark reports."""

from __future__ import annotations

import hashlib
from pathlib import Path


def safe_output_name(value: str) -> str:
    """Convert a symbol into a stable filesystem component."""
    return "".join(
        character if character.isalnum() or character in "._-" else "_" for character in value
    )


def tree_digest(root: Path, files: tuple[Path, ...]) -> str:
    """Hash relative names and file contents in deterministic order."""
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()

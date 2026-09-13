"""Shared method-file staging for flat assembly publications."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..core.content_hash import sha256_text


def stage_method_file(
    stage: Path,
    files: dict[str, dict[str, object]],
    seen: dict[str, str],
    relative_path: Path,
    content: str | bytes,
    kind: str,
    owner: str,
    method_id: str,
    diagnostics: tuple[str, ...],
) -> None:
    """Stage one deduplicated method artifact and record its bounded descriptor."""
    relative = relative_path.as_posix()
    digest = sha256_text(content) if isinstance(content, str) else _sha256_bytes(content)
    previous = seen.get(relative)
    if previous is not None and previous != digest:
        raise ValueError(f"Conflicting symbol method artifact: {relative}")
    if previous is not None:
        return
    seen[relative] = digest
    if isinstance(content, bytes):
        destination = stage / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        byte_count = len(content)
    else:
        destination = stage / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")
        byte_count = len(content.encode("utf-8"))
    files[relative] = {
        "kind": kind,
        "owner": owner,
        "method_id": method_id,
        "sha256": digest,
        "bytes": byte_count,
        "diagnostics": list(diagnostics),
    }


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

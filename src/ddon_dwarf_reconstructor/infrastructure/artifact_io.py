"""Small, shared filesystem primitives for source-bound evidence artifacts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..core.content_hash import sha256_bytes


def safe_relative_path(path: Path) -> Path:
    """Validate a descriptor path before it is joined to an artifact root."""
    if path.is_absolute() or path.root or path.drive or not path.parts or ".." in path.parts:
        raise ValueError(f"artifact path must be relative and contained: {path}")
    return path


def temporary_text(path: Path, content: str) -> Path:
    """Write durable UTF-8 text beside its target and return the temporary path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return temporary


def atomic_write_text(path: Path, content: str) -> None:
    """Publish text with a same-directory replace and cleanup on failure."""
    temporary: Path | None = None
    try:
        temporary = temporary_text(path, content)
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def content_sha256(content: str | bytes) -> str:
    """Hash rendered text or binary content using the canonical content contract."""
    return sha256_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


__all__ = ["atomic_write_text", "content_sha256", "safe_relative_path", "temporary_text"]

"""Outbound source-identity conversation used by deterministic exporters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SourceHashPort(Protocol):
    """Return the strong identity hash for an immutable source artifact."""

    def __call__(self, source_path: Path) -> str: ...

"""Typed requests and results for application-level header generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ...utils.path_utils import create_header_filename


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Immutable options for one generation workflow."""

    symbol: str
    full_hierarchy: bool = False
    single_file: bool = False
    include_metadata: bool = True
    output_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class HeaderBundle:
    """Deterministic generated headers keyed by their output filenames."""

    headers: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(sorted(self.headers.items()))))

    @classmethod
    def single(cls, symbol: str, content: str) -> HeaderBundle:
        """Create a one-file bundle using the canonical filename policy."""
        return cls({create_header_filename(symbol): content})

    def as_dict(self) -> dict[str, str]:
        """Return a mutable copy for output adapters and legacy callers."""
        return dict(self.headers)

    def only(self) -> str:
        """Return the sole header content, raising for multi-file results."""
        if len(self.headers) != 1:
            raise ValueError("HeaderBundle.only() requires exactly one generated header")
        return next(iter(self.headers.values()))

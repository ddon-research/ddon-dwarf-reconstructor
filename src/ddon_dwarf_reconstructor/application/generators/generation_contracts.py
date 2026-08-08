"""Typed requests and results for application-level header generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from ...core.path_policy import create_header_filename


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Immutable options for one generation workflow."""

    symbol: str
    full_hierarchy: bool = False
    single_file: bool = False
    include_metadata: bool = True
    output_dir: Path | None = None


GenerationStatus = Literal["success", "error"]


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    """Result for one requested symbol in a generation run."""

    symbol: str
    status: GenerationStatus
    headers: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return bounded structured data suitable for the JSONL log."""
        result: dict[str, object] = {
            "symbol": self.symbol,
            "status": self.status,
            "headers": list(self.headers),
        }
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass(frozen=True, slots=True)
class GenerationReport:
    """Deterministic per-symbol accounting for one generation run."""

    requested_symbols: tuple[str, ...]
    outcomes: tuple[GenerationOutcome, ...]
    published: bool

    def to_dict(self) -> dict[str, object]:
        """Return the complete bounded report for structured observability."""
        return {
            "requested_symbols": list(self.requested_symbols),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "published": self.published,
            "succeeded": sum(outcome.status == "success" for outcome in self.outcomes),
            "failed": sum(outcome.status == "error" for outcome in self.outcomes),
        }


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

    def only(self) -> str:
        """Return the sole header content, raising for multi-file results."""
        if len(self.headers) != 1:
            raise ValueError("HeaderBundle.only() requires exactly one generated header")
        return next(iter(self.headers.values()))

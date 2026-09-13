"""Typed requests and results for application-level header generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from ...core.content_hash import header_bundle_sha256
from ...core.path_policy import create_header_filename
from ...domain.models.dwarf import ClassInfo


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Immutable options for one generation workflow."""

    symbol: str
    full_hierarchy: bool = False
    single_file: bool = False
    include_metadata: bool = True
    output_dir: Path | None = None


GenerationStatus = Literal[
    "success",
    "partial",
    "blocked",
    "unavailable",
    "failed",
    "error",
]


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
            "failed": sum(outcome.status != "success" for outcome in self.outcomes),
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

    @property
    def sha256(self) -> str:
        """Return a deterministic digest of filenames and UTF-8 header bytes."""
        return header_bundle_sha256(self.headers)


@dataclass(frozen=True, slots=True)
class SymbolExtractionRequest:
    """Immutable request for one or more symbol dependency closures."""

    symbols: tuple[str, ...]
    include_metadata: bool = True
    max_depth: int = 10

    def __post_init__(self) -> None:
        symbols = tuple(symbol.strip() for symbol in self.symbols if symbol.strip())
        if not symbols:
            raise ValueError("SymbolExtractionRequest requires at least one symbol")
        if len(set(symbols)) != len(symbols):
            raise ValueError("SymbolExtractionRequest symbols must be unique")
        if self.max_depth < 1:
            raise ValueError("SymbolExtractionRequest max_depth must be positive")
        object.__setattr__(self, "symbols", symbols)


@dataclass(frozen=True, slots=True)
class SymbolExtractionResult:
    """One deduplicated symbol output plus ownership and provenance maps."""

    requested_symbols: tuple[str, ...]
    headers: Mapping[str, str]
    header_owners: Mapping[str, str]
    header_classes: Mapping[str, tuple[str, ...]]
    class_owners: Mapping[str, str]
    class_origins: Mapping[str, tuple[str, ...]]
    class_identities: Mapping[str, str]
    class_infos: Mapping[str, ClassInfo]
    class_aliases: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    root_statuses: Mapping[str, str] = field(default_factory=dict)
    configuration: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_symbols", tuple(self.requested_symbols))
        for name in (
            "headers",
            "header_owners",
            "header_classes",
            "class_owners",
            "class_origins",
            "class_identities",
            "class_infos",
            "class_aliases",
            "root_statuses",
            "configuration",
        ):
            value = getattr(self, name)
            object.__setattr__(self, name, MappingProxyType(dict(value)))

    @property
    def header_bundle(self) -> HeaderBundle:
        """Adapt relative symbol paths to the implementation report contract."""
        return HeaderBundle(self.headers)

    @property
    def header_count(self) -> int:
        return len(self.headers)

    @property
    def class_count(self) -> int:
        return len(self.class_infos)


__all__ = [
    "GenerationOutcome",
    "GenerationReport",
    "GenerationRequest",
    "HeaderBundle",
    "SymbolExtractionRequest",
    "SymbolExtractionResult",
]

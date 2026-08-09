"""Mutable state for one generation workflow session."""

from __future__ import annotations

from dataclasses import dataclass, field

from .application.generators import GenerationOutcome


@dataclass(slots=True)
class GenerationState:
    """State accumulated while one generator session processes symbols."""

    separate_symbol_bundles: bool
    success_count: int = 0
    failed_symbols: list[tuple[str, str]] = field(default_factory=list)
    outcomes: list[GenerationOutcome] = field(default_factory=list)
    pending_headers: dict[str, str] = field(default_factory=dict)
    pending_header_sources: dict[str, str] = field(default_factory=dict)
    pending_bundles: list[tuple[int, str, dict[str, str]]] = field(default_factory=list)

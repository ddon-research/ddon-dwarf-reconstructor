"""Ports for optional implementation-artifact enrichment."""

from __future__ import annotations

from typing import Protocol

from ..models.implementation_context import ImplementationContextEnrichment


class ImplementationContextEnrichmentProvider(Protocol):
    """Provide optional, source-bound context for a rendered method."""

    def get(
        self,
        method_id: str,
        default: ImplementationContextEnrichment | None = None,
    ) -> ImplementationContextEnrichment | None: ...


__all__ = ["ImplementationContextEnrichmentProvider"]

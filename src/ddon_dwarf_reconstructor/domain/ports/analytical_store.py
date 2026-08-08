"""Ports for analytical DWARF materialization and query backends."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

from ..models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationManifest,
    MaterializedUnit,
    QueryResult,
)


class DwarfMaterializationPort(Protocol):
    """Produce a complete source-bound analytical store."""

    def materialize(self, request: DwarfMaterializationRequest) -> MaterializationManifest: ...


class DwarfQueryPort(Protocol):
    """Read-only queries required by generation and knowledge export."""

    manifest: MaterializationManifest

    def iter_compilation_units(self) -> Iterable[MaterializedUnit]: ...

    def get_compilation_unit(self, unit_offset: int) -> QueryResult: ...

    def get_die(self, die_offset: int) -> QueryResult:
        """Return one DIE while preserving unavailable/partial evidence."""
        ...

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        """Return definition candidates in deterministic order."""
        ...

    def find_primary_definition(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        """Return the selected primary definition without expanding duplicates."""
        ...

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        """Resolve an implementation through DWARF specification references."""
        ...

    def children(self, die_offset: int) -> QueryResult: ...

    def parent(self, die_offset: int) -> QueryResult: ...

    def references(self, die_offset: int) -> QueryResult: ...


class DwarfStoreLoader(Protocol):
    """Load and validate a source-bound store manifest."""

    def load(self, manifest_path: Path) -> DwarfQueryPort: ...


class DwarfStorePublisher(Protocol):
    """Publish optional projections from the canonical typed row contract."""

    def publish(self, manifest: MaterializationManifest) -> Sequence[Path]: ...

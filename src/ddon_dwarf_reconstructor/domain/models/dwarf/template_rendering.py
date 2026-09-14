"""Evidence decisions consumed by rendering without changing concrete DWARF data."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TemplateRendering:
    """One specialization's projection into a planned template family."""

    primary: str
    declaration: str
    mode: Literal["generic", "explicit", "blocked"]
    representative: bool = True
    substitutions: tuple[tuple[str, str], ...] = ()
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateFamilyPlan:
    """Immutable family membership, emission policy, and retained provenance."""

    primary: str
    mode: Literal["generic", "explicit", "blocked"]
    declaration: str
    members: tuple[str, ...]
    origins: tuple[str, ...]
    provenance: tuple[tuple[str, int | None, int | None], ...]
    diagnostics: tuple[str, ...] = ()
    definition_signatures: tuple[tuple[str, str], ...] = ()

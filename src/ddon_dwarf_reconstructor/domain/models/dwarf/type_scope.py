"""Source-derived lexical scopes; spelling alone never determines scope kind."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ScopeComponent:
    """One enclosing declaration in a source-bound DIE graph."""

    name: str
    kind: Literal["namespace", "class", "struct", "union"]
    cu_offset: int | None = None
    die_offset: int | None = None


@dataclass(frozen=True, slots=True)
class TypeScope:
    """Ordered lexical ancestry, including whether ancestry was recoverable."""

    components: tuple[ScopeComponent, ...] = ()
    complete: bool = True

    def qualify(self, name: str) -> str:
        prefix = "::".join(component.name for component in self.components)
        if not prefix or name.startswith(prefix + "::"):
            return name
        return f"{prefix}::{name}"

    @property
    def namespace_only(self) -> bool:
        """Whether a namespace wrapper can represent this complete ancestry."""
        return self.complete and all(part.kind == "namespace" for part in self.components)

    @property
    def containing_aggregate(self) -> str | None:
        """Qualified nearest aggregate owner, without guessing from separators."""
        for index in range(len(self.components) - 1, -1, -1):
            if self.components[index].kind != "namespace":
                return "::".join(part.name for part in self.components[: index + 1])
        return None

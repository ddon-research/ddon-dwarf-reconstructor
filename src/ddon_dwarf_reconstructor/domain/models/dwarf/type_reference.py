"""Structured C++ type-reference and declarator values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TypeDeclarator:
    """Syntax-neutral representation of a C++ declarator chain."""

    base_name: str
    qualifiers: tuple[str, ...] = ()
    pointer_depth: int = 0
    reference_kind: str | None = None
    array_dimensions: tuple[int | None, ...] = ()
    function_parameters: tuple[str, ...] | None = None
    pointer_to_member_of: str | None = None
    unresolved: bool = False

    def __post_init__(self) -> None:
        if self.pointer_depth < 0:
            raise ValueError("pointer_depth must be non-negative")

    def render(self) -> str:
        """Render the declarator without changing its stored evidence."""
        qualifier_prefix = " ".join(self.qualifiers)
        base = f"{qualifier_prefix} {self.base_name}" if qualifier_prefix else self.base_name
        member_prefix = f"{self.pointer_to_member_of}::*" if self.pointer_to_member_of else ""
        indirection = member_prefix or "*" * self.pointer_depth
        reference = self.reference_kind or ""
        rendered = f"{base}{indirection}{reference}"
        if self.function_parameters is not None:
            rendered += f"({', '.join(self.function_parameters)})"
        for dimension in self.array_dimensions:
            rendered += f"[{'' if dimension is None else dimension}]"
        return rendered


@dataclass(frozen=True, slots=True)
class TypeReference:
    """A type declarator plus the optional DWARF evidence offset."""

    declarator: TypeDeclarator
    die_offset: int | None = None

    @property
    def name(self) -> str:
        """Return the stable rendered name used by header generation."""
        return self.declarator.render()

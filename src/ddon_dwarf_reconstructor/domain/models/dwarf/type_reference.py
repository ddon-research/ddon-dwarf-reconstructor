"""Structured C++ type-reference and declarator values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .type_scope import TypeScope


@dataclass(frozen=True, slots=True)
class DeclaratorLayer:
    """One outer-to-inner operation; qualifiers bind to this operation only."""

    kind: Literal["pointer", "reference", "rvalue_reference", "member_pointer", "array", "function"]
    qualifiers: tuple[str, ...] = ()
    owner: TypeReference | None = None
    extent: int | None = None
    parameters: tuple[TypeReference, ...] = ()
    variadic: bool = False
    ref_qualifier: str | None = None
    noexcept: bool = False

    def apply(self, name: str, *, parenthesize: bool = False) -> str:
        """Insert one operation around a named or abstract declarator."""
        if self.kind == "array":
            return f"{name}[{'' if self.extent is None else self.extent}]"
        if self.kind == "function":
            return self._function_declaration(name)
        operator = {"pointer": "*", "reference": "&", "rvalue_reference": "&&"}.get(self.kind)
        if self.kind == "member_pointer":
            operator = f"{self.owner.name if self.owner is not None else 'unknown_type'}::*"
        qualifiers = " ".join(self.qualifiers)
        decorated = f"{operator}{qualifiers}{' ' if qualifiers and name else ''}{name}"
        return f"({decorated})" if parenthesize else decorated

    def _function_declaration(self, name: str) -> str:
        arguments = [parameter.name for parameter in self.parameters]
        if self.variadic:
            arguments.append("...")
        suffix = [*self.qualifiers]
        if self.ref_qualifier:
            suffix.append(self.ref_qualifier)
        if self.noexcept:
            suffix.append("noexcept")
        tail = " " + " ".join(suffix) if suffix else ""
        return f"{name}({', '.join(arguments)}){tail}"


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
    layers: tuple[DeclaratorLayer, ...] = ()

    def __post_init__(self) -> None:
        if self.pointer_depth < 0:
            raise ValueError("pointer_depth must be non-negative")

    def render(self, identifier: str = "") -> str:
        """Render the declarator without changing its stored evidence."""
        qualifier_prefix = " ".join(self.qualifiers)
        base = f"{qualifier_prefix} {self.base_name}" if qualifier_prefix else self.base_name
        if self.layers:
            return self._render_layers(base, identifier)
        return self._render_flat(base, identifier)

    def _render_layers(self, base: str, identifier: str) -> str:
        declarator = identifier
        for index, layer in enumerate(self.layers):
            following = self.layers[index + 1 : index + 2]
            parenthesize = bool(following and following[0].kind in {"array", "function"})
            declarator = layer.apply(declarator, parenthesize=parenthesize)
        separator = (
            " "
            if identifier or (declarator.startswith("(") and self.layers[0].kind != "function")
            else ""
        )
        return f"{base}{separator}{declarator}"

    def _render_flat(self, base: str, identifier: str) -> str:
        member_prefix = f"{self.pointer_to_member_of}::*" if self.pointer_to_member_of else ""
        indirection = member_prefix or "*" * self.pointer_depth
        reference = self.reference_kind or ""
        rendered = f"{base}{indirection}{reference}{' ' if identifier else ''}{identifier}"
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
    template_arguments: tuple[TypeReference, ...] = ()
    cu_offset: int | None = None
    kind: str | None = None
    scope: TypeScope = TypeScope()
    alias_target: TypeReference | None = None
    diagnostics: tuple[str, ...] = ()
    declaration_access: Literal["public", "protected", "private"] | None = None
    is_anonymous: bool = False

    def references(self) -> tuple[TypeReference, ...]:
        """Return named evidence dependencies, including callable owners/arguments."""
        result: list[TypeReference] = [self]
        for layer in self.declarator.layers:
            if layer.owner is not None:
                result.extend(layer.owner.references())
            for parameter in layer.parameters:
                result.extend(parameter.references())
        for argument in self.template_arguments:
            result.extend(argument.references())
        if self.alias_target is not None:
            result.extend(self.alias_target.references())
        return tuple(result)

    @property
    def name(self) -> str:
        """Return the stable rendered name used by header generation."""
        return self.declarator.render()

"""Enum definitions and forwards from distinct scopedness and representation facts."""

from __future__ import annotations

from ...models.dwarf.enum_info import EnumInfo
from .rendering.type_policy import TypeExpressionPolicy


class EnumDeclarationError(ValueError):
    """The available evidence cannot justify an enum declaration."""


def enum_definition_lines(enum: EnumInfo, name: str, *, indent: str = "") -> list[str]:
    """Render a complete enum at either class or namespace scope."""
    declaration = enum_head(enum, name if enum.defining_alias is None else "")
    head = f"typedef {declaration}" if enum.defining_alias is not None else declaration
    lines = [f"{indent}{head}", f"{indent}{{"]
    for index, enumerator in enumerate(enum.enumerators):
        comma = "," if index < len(enum.enumerators) - 1 else ""
        lines.append(f"{indent}    {enumerator.name} = {enumerator.value}{comma}")
    terminator = f"}} {name};" if enum.defining_alias is not None else "};"
    return [*lines, f"{indent}{terminator}"]


def enum_head(enum: EnumInfo, name: str) -> str:
    """Render a definition head without claiming original fixed-base syntax."""
    if enum.scoped is None:
        raise EnumDeclarationError(
            f"unknown enum scopedness: {enum.name} CU={enum.cu_offset} DIE={enum.die_offset}"
        )
    if enum.scoped:
        if not name or enum.defining_alias is not None:
            raise EnumDeclarationError(f"scoped enum lacks a named definition: {enum.name}")
        representation = enum.representation_type
        if representation is None or not TypeExpressionPolicy.is_integral(representation.name):
            raise EnumDeclarationError(f"scoped enum lacks integral representation: {enum.name}")
        return f"enum class {name} : {representation.name}"
    if enum.fixed_base_evidence is True:
        return _fixed_unscoped_head(enum, name)
    return f"enum{' ' + name if name else ''}"


def _fixed_unscoped_head(enum: EnumInfo, name: str) -> str:
    representation = enum.representation_type
    if representation is None or not TypeExpressionPolicy.is_integral(representation.name):
        raise EnumDeclarationError(f"fixed enum lacks integral base: {enum.name}")
    if not name:
        raise EnumDeclarationError(f"fixed enum lacks a name: {enum.name}")
    return f"enum {name} : {representation.name}"


def enum_forward(enum: EnumInfo, name: str) -> str | None:
    """Only a known scoped enum with a known representation can be opaque."""
    if enum.scoped is None or not name or enum.defining_alias is not None:
        return None
    if enum.scoped or enum.fixed_base_evidence is True:
        return f"{enum_head(enum, name)};"
    return None

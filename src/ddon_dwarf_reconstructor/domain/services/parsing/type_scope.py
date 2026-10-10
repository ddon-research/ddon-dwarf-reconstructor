"""Recover lexical ancestry and boolean attributes from source DIE evidence."""

from __future__ import annotations

from typing import Literal

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ...models.dwarf.type_scope import ScopeComponent, TypeScope

_SCOPE_KINDS: dict[str, Literal["namespace", "class", "struct", "union"]] = {
    "DW_TAG_namespace": "namespace",
    "DW_TAG_class_type": "class",
    "DW_TAG_structure_type": "struct",
    "DW_TAG_union_type": "union",
}


def flag(die: DwarfEntry, name: str) -> bool:
    """A present false flag is false, including DW_FORM_flag values."""
    attribute = die.attributes.get(name)
    return attribute is not None and bool(attribute.value)


def die_key(die: DwarfEntry) -> tuple[int | None, int | None]:
    """Retain zero offsets and avoid treating test doubles as identities."""
    cu_offset = getattr(getattr(die, "cu", None), "cu_offset", None)
    offset = getattr(die, "offset", None)
    return (
        cu_offset if isinstance(cu_offset, int) else None,
        offset if isinstance(offset, int) else None,
    )


def referenced_die(die: DwarfEntry, name: str = "DW_AT_type") -> DwarfEntry | None:
    """Read a reference through its adapter, never as a raw absolute offset."""
    if name not in die.attributes:
        return None
    return die.get_DIE_from_attribute(name)


def lexical_scope(die: DwarfEntry) -> TypeScope:
    """Follow parent declarations and distinguish aggregate and namespace scopes."""
    parts: list[ScopeComponent] = []
    visited: set[tuple[int | None, int | None]] = set()
    current = referenced_die(die, "DW_AT_specification") or die
    while True:
        try:
            parent = current.get_parent()
        except AttributeError:
            return TypeScope(tuple(reversed(parts)), complete=False)
        if parent is None:
            return TypeScope(tuple(reversed(parts)))
        tag = getattr(parent, "tag", None)
        if tag in {"DW_TAG_compile_unit", "DW_TAG_type_unit", "DW_TAG_partial_unit"}:
            return TypeScope(tuple(reversed(parts)))
        if not isinstance(tag, str) or tag not in _SCOPE_KINDS:
            return TypeScope(tuple(reversed(parts)), complete=False)
        key = die_key(parent)
        if key in visited:
            return TypeScope(tuple(reversed(parts)), complete=False)
        visited.add(key)
        attribute = parent.attributes.get("DW_AT_name")
        if attribute is None:
            return TypeScope(tuple(reversed(parts)), complete=False)
        parts.append(ScopeComponent(decode_dwarf_string(attribute.value), _SCOPE_KINDS[tag], *key))
        current = parent


def qualified_die_name(die: DwarfEntry) -> str | None:
    """Return a source spelling in its evidenced lexical scope."""
    attribute = die.attributes.get("DW_AT_name")
    if attribute is None:
        specification = referenced_die(die, "DW_AT_specification")
        if specification is None or die_key(specification) == die_key(die):
            return None
        attribute = specification.attributes.get("DW_AT_name")
    if attribute is None:
        return None
    return lexical_scope(die).qualify(decode_dwarf_string(attribute.value))

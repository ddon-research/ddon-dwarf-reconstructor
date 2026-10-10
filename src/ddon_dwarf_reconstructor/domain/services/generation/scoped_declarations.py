"""Declaration placement backed by lexical evidence, never qualified spelling."""

from __future__ import annotations

import re

from ...models.dwarf.type_reference import TypeReference
from ...models.dwarf.type_scope import TypeScope


def scoped_declaration(
    name: str, kind: str = "class", scope: TypeScope | None = None
) -> str | None:
    """Declare an aggregate only where its enclosing namespaces are proven.

    Enclosing aggregate members require the owner's declaration. Templates and
    enums require additional signature evidence supplied by their own plans.
    """
    if scope is None:
        return f"{kind} {name};" if re.fullmatch(r"[A-Za-z_]\w*", name) else None
    if not scope.namespace_only:
        return None
    namespace = "::".join(component.name for component in scope.components)
    prefix = namespace + "::" if namespace else ""
    if prefix and not name.startswith(prefix):
        return None
    local_name = name[len(prefix) :]
    if not re.fullmatch(r"[A-Za-z_]\w*", local_name):
        return None
    declaration = f"{kind} {local_name};"
    return f"namespace {namespace} {{ {declaration} }}" if namespace else declaration


def reference_forward_declaration(reference: TypeReference) -> str | None:
    """Keep aliases and nested types out of aggregate forward declarations."""
    kind = {
        "DW_TAG_class_type": "class",
        "DW_TAG_structure_type": "struct",
        "DW_TAG_union_type": "union",
    }.get(reference.kind or "")
    if kind is None or reference.diagnostics:
        return None
    return scoped_declaration(reference.declarator.base_name, kind, reference.scope)

"""Fail-closed validation for symbol-oriented header bundles."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...domain.models.dwarf import ClassInfo

if TYPE_CHECKING:
    from .symbol_definition_graph import CanonicalDefinitionGraph

_COMPLETE_DEFINITION_RE = re.compile(r"(?m)^\s*(?:class|struct|union)\s+([A-Za-z_]\w*)\b[^{;]*\{")
_INCLUDE_RE = re.compile(r'(?m)^\s*#include\s+"([^"]+)"\s*$')


def complete_definition_names(content: str) -> list[str]:
    """Return qualified C++ names for complete class definitions in a header."""
    matches = tuple(_COMPLETE_DEFINITION_RE.finditer(content))
    starts = {match.start(): match.group(1) for match in matches}
    openings = {match.end() - 1: match.group(1) for match in matches}
    scopes: list[str | None] = []
    names: list[str] = []
    for index, character in enumerate(content):
        class_name = starts.get(index)
        if class_name is not None:
            enclosing = [scope for scope in scopes if scope is not None]
            names.append("::".join((*enclosing, class_name)))
        if character == "{":
            scopes.append(openings.get(index))
        elif character == "}" and scopes:
            scopes.pop()
    return names


def validate_rendered_headers(
    headers: Mapping[str, str],
    paths: Mapping[str, tuple[str, tuple[str, ...]]],
    class_infos: Mapping[str, ClassInfo],
    class_owners: Mapping[str, str],
) -> None:
    """Fail closed when publication would contain an internally invalid bundle."""
    header_paths = set(headers)
    assigned = _assigned_header_classes(headers, paths)
    _validate_class_assignments(assigned, class_infos, class_owners)
    for path, content in sorted(headers.items()):
        _validate_header_content(path, content, header_paths, paths, class_infos)


def _assigned_header_classes(
    headers: Mapping[str, str], paths: Mapping[str, tuple[str, tuple[str, ...]]]
) -> dict[str, list[str]]:
    assigned: dict[str, list[str]] = {}
    for path, (_owner, classes) in paths.items():
        if path not in headers:
            raise ValueError(f"Missing rendered symbol header: {path}")
        for class_name in classes:
            assigned.setdefault(class_name, []).append(path)
    return assigned


def _validate_class_assignments(
    assigned: Mapping[str, list[str]],
    class_infos: Mapping[str, ClassInfo],
    class_owners: Mapping[str, str],
) -> None:
    expected = set(class_infos)
    if set(assigned) != expected:
        missing = sorted(expected - set(assigned))
        extra = sorted(set(assigned) - expected)
        raise ValueError(
            "Symbol header ownership does not cover the reachable closure"
            f"; missing={missing!r}, extra={extra!r}"
        )
    duplicate_owners = {
        class_name: owners for class_name, owners in assigned.items() if len(owners) != 1
    }
    if duplicate_owners:
        raise ValueError(f"Symbol definitions have multiple owners: {duplicate_owners!r}")
    missing_owner = sorted(class_name for class_name in expected if class_name not in class_owners)
    if missing_owner:
        raise ValueError(f"Reachable symbol definitions lack owners: {missing_owner!r}")


def _validate_header_content(
    path: str,
    content: str,
    header_paths: set[str],
    paths: Mapping[str, tuple[str, tuple[str, ...]]],
    class_infos: Mapping[str, ClassInfo],
) -> None:
    _validate_header_includes(path, content, header_paths)
    namespace_names = [
        class_infos[name].name for name in paths[path][1] if class_infos[name].kind == "namespace"
    ]
    if namespace_names:
        _validate_namespace_header(path, content, namespace_names)
        return
    _validate_complete_definitions(path, content, paths[path][1], class_infos)


def _validate_header_includes(path: str, content: str, header_paths: set[str]) -> None:
    """Ensure every rewritten include resolves within the staged bundle."""
    for include in _INCLUDE_RE.findall(content):
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), include))
        if resolved not in header_paths:
            raise ValueError(f"Generated include does not exist: {path} -> {include}")


def _validate_namespace_header(path: str, content: str, namespace_names: list[str]) -> None:
    if len(namespace_names) != 1 or f"namespace {namespace_names[0]}" not in content:
        raise ValueError(f"Generated namespace header is incomplete: {path}")


def _validate_complete_definitions(
    path: str,
    content: str,
    class_names: tuple[str, ...],
    class_infos: Mapping[str, ClassInfo],
) -> None:
    rendered_names = complete_definition_names(content)
    counts = {name: rendered_names.count(name) for name in set(rendered_names)}
    duplicate_names = sorted(name for name, count in counts.items() if count > 1)
    if duplicate_names:
        raise ValueError(
            f"Generated header contains duplicate complete definitions: {path}: {duplicate_names!r}"
        )
    expected_names = {_rendered_class_name(class_infos[class_name]) for class_name in class_names}
    missing_names = sorted(expected_names - set(rendered_names))
    if missing_names:
        raise ValueError(
            f"Generated header omitted reachable definitions: {path}: {missing_names!r}"
        )


def _rendered_class_name(class_info: ClassInfo) -> str:
    if class_info.containing_type and class_info.qualified_name:
        return class_info.qualified_name
    name = class_info.name.strip()
    template_primary, separator, _arguments = name.partition("<")
    if separator:
        return template_primary.rsplit("::", 1)[-1].strip()
    return name.rsplit("::", 1)[-1]


def root_statuses(
    graph: CanonicalDefinitionGraph, diagnostics: tuple[str, ...] = ()
) -> dict[str, str]:
    """Report partial roots when their reachable evidence is incomplete."""
    return {
        symbol: root_status(graph, symbol, root_key, diagnostics)
        for symbol, root_key in sorted(graph.root_keys.items())
    }


def root_status(
    graph: CanonicalDefinitionGraph,
    symbol: str,
    root_key: str,
    diagnostics: tuple[str, ...],
) -> str:
    root_info = graph.class_infos[root_key]
    origins = {name for name, values in graph.origins.items() if symbol in values}
    relevant = tuple(
        diagnostic
        for diagnostic in tuple(graph.diagnostics) + diagnostics
        if any(
            diagnostic_mentions_origin(diagnostic, name, graph.class_infos[name])
            for name in origins
        )
    )
    incomplete = any(
        marker in diagnostic
        for diagnostic in relevant
        for marker in ("unresolved", "declaration-only", "conflicting", "cyclic")
    )
    return "partial" if root_info.is_declaration or incomplete else "success"


def diagnostic_mentions_origin(diagnostic: str, name: str, class_info: ClassInfo) -> bool:
    """Return whether a diagnostic belongs to a class or its member/signature context."""
    candidates = {name, class_info.name}
    if class_info.qualified_name:
        candidates.add(class_info.qualified_name)

    if " dependency for " in diagnostic:
        _, _, rest = diagnostic.partition(" dependency for ")
        owner = rest.split("::", 1)[0].split(":", 1)[0].strip()
        return owner in candidates

    if "conflicting complete definitions for " in diagnostic:
        _, _, rest = diagnostic.partition("conflicting complete definitions for ")
        display = rest.split(":", 1)[0].strip()
        return display in candidates

    if "declaration-only definition for " in diagnostic:
        _, _, rest = diagnostic.partition("declaration-only definition for ")
        display = rest.strip()
        return display in candidates

    if "cyclic by-value dependency recovered for symbol rendering: " in diagnostic:
        _, _, rest = diagnostic.partition(
            "cyclic by-value dependency recovered for symbol rendering: "
        )
        components = {item.strip() for item in rest.split(",")}
        return any(c in components for c in candidates)

    return name in diagnostic


__all__ = [
    "complete_definition_names",
    "diagnostic_mentions_origin",
    "root_status",
    "root_statuses",
    "validate_rendered_headers",
]

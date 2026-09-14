"""Fail-closed validation for symbol-oriented header bundles."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...domain.models.dwarf import ClassInfo

if TYPE_CHECKING:
    from .symbol_definition_graph import CanonicalDefinitionGraph

_AGGREGATE_START_RE = re.compile(r"(?m)^\s*(?:class|struct|union)\b")
_ATTR_RE = re.compile(r"__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)\s*")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")
_INCLUDE_RE = re.compile(r'(?m)^\s*#include\s+"([^"]+)"\s*$')


def _match_template_arguments(content: str, start: int) -> tuple[str, int] | None:
    if start >= len(content) or content[start] != "<":
        return "", start
    depth = 1
    index = start + 1
    while index < len(content) and depth > 0:
        character = content[index]
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif character in "{;\n":
            return None
        index += 1
    return (content[start:index], index) if depth == 0 else None


def _parse_definition_at(content: str, start: int) -> tuple[int, str] | None:
    index = start
    while index < len(content) and content[index].isspace():
        index += 1
    attribute_match = _ATTR_RE.match(content, index)
    if attribute_match:
        index = attribute_match.end()
    identifier_match = _IDENTIFIER_RE.match(content, index)
    if identifier_match is None:
        return None
    class_name = identifier_match.group(0)
    arguments = _match_template_arguments(content, identifier_match.end())
    if arguments is None:
        return None
    suffix, index = arguments
    class_name += suffix
    while index < len(content) and content[index] not in "{;":
        index += 1
    if index < len(content) and content[index] == "{":
        return (index, class_name)
    return None


def _definition_matches(content: str) -> list[tuple[int, int, str]]:
    results = []
    for match in _AGGREGATE_START_RE.finditer(content):
        parsed = _parse_definition_at(content, match.end())
        if parsed is not None:
            results.append((match.start(), parsed[0], parsed[1]))
    return results


def complete_definition_names(content: str) -> list[str]:
    """Return qualified C++ names for complete class definitions in a header."""
    matches = tuple(_definition_matches(content))
    starts = {match[0]: match[2] for match in matches}
    openings = {match[1]: match[2] for match in matches}
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
    _validate_template_locations(headers, class_infos)


def _expected_template_definitions(infos: Mapping[str, ClassInfo]) -> set[str]:
    return {
        _rendered_class_name(info)
        for info in infos.values()
        if info.template_rendering is not None and info.template_rendering.mode != "blocked"
    }


def _validate_template_locations(
    headers: Mapping[str, str], infos: Mapping[str, ClassInfo]
) -> None:
    """Require a unique definition location for every planned emitted template."""
    locations: dict[str, list[str]] = {name: [] for name in _expected_template_definitions(infos)}
    for path, content in headers.items():
        for name in complete_definition_names(content):
            if name in locations:
                locations[name].append(path)
    invalid = {name: paths for name, paths in locations.items() if len(paths) != 1}
    if invalid:
        raise ValueError(f"Template definitions require one canonical location: {invalid!r}")


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
    expected_names = {
        _rendered_class_name(class_infos[name])
        for name in class_names
        if (plan := class_infos[name].template_rendering) is None or plan.mode != "blocked"
    }
    missing_names = sorted(expected_names - set(rendered_names))
    if missing_names:
        raise ValueError(
            f"Generated header omitted reachable definitions: {path}: {missing_names!r}"
        )


def _rendered_class_name(class_info: ClassInfo) -> str:
    if class_info.containing_type and class_info.qualified_name:
        return class_info.qualified_name
    name = class_info.name.strip()
    plan = class_info.template_rendering
    if plan is not None and plan.mode == "explicit":
        return re.sub(r"\b[A-Za-z_]\w*::(?=[A-Za-z_]\w*)", "", name)
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

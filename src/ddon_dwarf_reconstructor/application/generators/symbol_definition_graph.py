"""Canonical definition graph for symbol-oriented generation."""

from __future__ import annotations

import json
from collections import Counter, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import TYPE_CHECKING, Any

from ...core.content_hash import sha256_text
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation.alias_evidence import source_aliases
from ...domain.services.generation.dependency_extractor import DependencyExtractor
from ...domain.services.generation.header_type_planning import HeaderTypePlanningService

if TYPE_CHECKING:
    from ..generation.runtime import GenerationRuntime


class CanonicalDefinitionGraph:
    """Reachable, canonical class definitions and their provenance."""

    def __init__(
        self,
        class_infos: Mapping[str, ClassInfo],
        hierarchy_order: Iterable[str],
        root_keys: Mapping[str, str],
        origins: Mapping[str, set[str]],
        dependencies: Mapping[str, set[str]],
        aliases: Mapping[str, tuple[str, ...]],
        diagnostics: Iterable[str],
    ) -> None:
        self.class_infos = dict(class_infos)
        self.hierarchy_order = list(dict.fromkeys(hierarchy_order))
        self.root_keys = dict(root_keys)
        self.origins = {name: set(values) for name, values in origins.items()}
        self.dependencies = {name: set(values) for name, values in dependencies.items()}
        self.aliases = dict(aliases)
        self.diagnostics = tuple(sorted(set(diagnostics)))

    @property
    def identities(self) -> dict[str, str]:
        """Return canonical identity text keyed by canonical class key."""
        return {name: identity_text(info) for name, info in self.class_infos.items()}


@dataclass(frozen=True, slots=True)
class _DefinitionIndexes:
    """Lookup indexes built once for one canonicalization boundary."""

    by_offset: Mapping[int, list[str]]
    by_name: Mapping[str, list[str]]
    by_key: Mapping[str, list[str]]
    by_display: Mapping[str, list[str]]


def build_canonical_definition_graph(
    context: GenerationRuntime,
    symbols: Iterable[str],
    class_infos: Mapping[str, ClassInfo],
    hierarchy_order: Iterable[str],
) -> CanonicalDefinitionGraph:
    """Canonicalize definitions and retain only the requested-root closure."""
    canonical, old_to_new, aliases, diagnostics = _canonicalize(class_infos)
    roots = _resolve_roots(
        symbols,
        old_to_new,
        canonical,
        _definition_indexes(class_infos),
    )
    dependencies = _dependency_edges(context, canonical, class_infos, old_to_new)
    origins = _reachable_origins(roots, dependencies)
    reachable = {name for name, values in origins.items() if values}
    dropped = len(canonical) - len(reachable)
    if dropped:
        diagnostics.append(f"dropped {dropped} unreachable class definitions")
    embedded = _embedded_definition_keys(canonical)
    root_values = set(roots.values())
    collapsed = (embedded & reachable) - root_values
    if collapsed:
        diagnostics.append(f"collapsed {len(collapsed)} nested class definitions into owners")
    retained = reachable - collapsed
    filtered_infos = {name: canonical[name] for name in sorted(retained)}
    filtered_dependencies = {
        name: dependencies.get(name, set()) & retained for name in filtered_infos
    }
    filtered_origins = {name: origins[name] for name in filtered_infos}
    filtered_aliases = {name: aliases.get(name, ()) for name in filtered_infos}
    order = _canonical_order(hierarchy_order, old_to_new, retained)
    return CanonicalDefinitionGraph(
        filtered_infos,
        order,
        roots,
        filtered_origins,
        filtered_dependencies,
        filtered_aliases,
        diagnostics,
    )


def _canonicalize(
    class_infos: Mapping[str, ClassInfo],
) -> tuple[dict[str, ClassInfo], dict[str, str], dict[str, tuple[str, ...]], list[str]]:
    exact_representatives, old_to_new = _exact_identity_representatives(class_infos)
    canonical: dict[str, ClassInfo] = {}
    aliases: dict[str, tuple[str, ...]] = {}
    diagnostics: list[str] = []
    for display, entries in _entries_by_display(exact_representatives):
        _canonicalize_display(
            display,
            entries,
            canonical,
            aliases,
            old_to_new,
            diagnostics,
        )
    _flatten_identity_aliases(old_to_new, canonical)
    return canonical, old_to_new, aliases, diagnostics


def _flatten_identity_aliases(
    old_to_new: dict[str, str], canonical: Mapping[str, ClassInfo]
) -> None:
    """Resolve original class keys through exact and cross-CU merge stages."""
    for source_key in old_to_new:
        target = old_to_new[source_key]
        visited = {source_key}
        while target not in canonical:
            if target in visited or target not in old_to_new:
                raise ValueError(f"Unresolved canonical definition identity: {source_key}")
            visited.add(target)
            target = old_to_new[target]
        old_to_new[source_key] = target


def _exact_identity_representatives(
    class_infos: Mapping[str, ClassInfo],
) -> tuple[list[tuple[str, ClassInfo, tuple[str, ...]]], dict[str, str]]:
    identity_groups: dict[tuple[object, ...], list[tuple[str, ClassInfo]]] = {}
    for name, info in class_infos.items():
        identity_groups.setdefault(definition_identity(info), []).append((name, info))

    exact_representatives: list[tuple[str, ClassInfo, tuple[str, ...]]] = []
    old_to_new: dict[str, str] = {}
    for _identity, entries in sorted(identity_groups.items(), key=lambda item: str(item[0])):
        _representative_name, representative = max(entries, key=lambda item: _richness(item[1]))
        representative = replace(
            representative, source_aliases=source_aliases(info for _, info in entries)
        )
        identity_key = identity_key_for(representative)
        exact_representatives.append(
            (identity_key, representative, tuple(identity_text(info) for _, info in entries))
        )
        for name, _info in entries:
            old_to_new[name] = identity_key
    return exact_representatives, old_to_new


def _entries_by_display(
    exact_representatives: Iterable[tuple[str, ClassInfo, tuple[str, ...]]],
) -> list[tuple[str, list[tuple[str, ClassInfo, tuple[str, ...]]]]]:
    by_definition: dict[tuple[str, str], list[tuple[str, ClassInfo, tuple[str, ...]]]] = {}
    for key, info, identity_aliases in exact_representatives:
        display = info.qualified_name or info.name
        fingerprint = definition_fingerprint(info)
        by_definition.setdefault((display, fingerprint), []).append((key, info, identity_aliases))

    grouped_by_display: dict[str, list[tuple[str, ClassInfo, tuple[str, ...]]]] = {}
    for (display, _fingerprint), entries in by_definition.items():
        grouped_by_display.setdefault(display, []).extend(entries)
    return [(display, entries) for display, entries in sorted(grouped_by_display.items())]


def _canonicalize_display(
    display: str,
    entries: list[tuple[str, ClassInfo, tuple[str, ...]]],
    canonical: dict[str, ClassInfo],
    aliases: dict[str, tuple[str, ...]],
    old_to_new: dict[str, str],
    diagnostics: list[str],
) -> None:
    complete, declarations = _split_definition_entries(entries)
    groups = _definition_groups(complete or declarations)
    _append_conflict_diagnostic(display, groups if complete else [], diagnostics)
    selected_keys = _select_definition_groups(groups, canonical, aliases, old_to_new)
    _map_declarations(
        display, complete, declarations, selected_keys, canonical, old_to_new, diagnostics
    )


def _split_definition_entries(
    entries: list[tuple[str, ClassInfo, tuple[str, ...]]],
) -> tuple[
    list[tuple[str, ClassInfo, tuple[str, ...]]],
    list[tuple[str, ClassInfo, tuple[str, ...]]],
]:
    complete: list[tuple[str, ClassInfo, tuple[str, ...]]] = []
    declarations: list[tuple[str, ClassInfo, tuple[str, ...]]] = []
    for entry in entries:
        (declarations if entry[1].is_declaration else complete).append(entry)
    return complete, declarations


def _map_declarations(
    display: str,
    complete: list[tuple[str, ClassInfo, tuple[str, ...]]],
    declarations: list[tuple[str, ClassInfo, tuple[str, ...]]],
    selected_keys: list[str],
    canonical: Mapping[str, ClassInfo],
    old_to_new: dict[str, str],
    diagnostics: list[str],
) -> None:
    if complete and declarations:
        fallback_key = max(selected_keys, key=lambda key: _richness(canonical[key]))
        for key, _info, _aliases in declarations:
            old_to_new[key] = fallback_key
        return
    if declarations:
        diagnostics.append(f"declaration-only definition for {display}")


def _append_conflict_diagnostic(
    display: str,
    groups: list[list[tuple[str, ClassInfo, tuple[str, ...]]]],
    diagnostics: list[str],
) -> None:
    if len(groups) > 1:
        diagnostics.append(
            f"conflicting complete definitions for {display}: "
            + ", ".join(sorted(identity_text(entry[1]) for group in groups for entry in group))
        )


def _select_definition_groups(
    groups: list[list[tuple[str, ClassInfo, tuple[str, ...]]]],
    canonical: dict[str, ClassInfo],
    aliases: dict[str, tuple[str, ...]],
    old_to_new: dict[str, str],
) -> list[str]:
    selected_keys: list[str] = []
    for group in groups:
        selected_key, selected_info, _ = max(group, key=lambda item: _richness(item[1]))
        selected_info = replace(
            selected_info, source_aliases=source_aliases(info for _, info, _ in group)
        )
        canonical[selected_key] = selected_info
        aliases[selected_key] = tuple(sorted({alias for item in group for alias in item[2]}))
        selected_keys.append(selected_key)
        for key, _info, _aliases in group:
            old_to_new[key] = selected_key
    return selected_keys


def _definition_groups(
    entries: list[tuple[str, ClassInfo, tuple[str, ...]]],
) -> list[list[tuple[str, ClassInfo, tuple[str, ...]]]]:
    by_shape: dict[str, list[tuple[str, ClassInfo, tuple[str, ...]]]] = {}
    for entry in entries:
        shape = definition_fingerprint(replace(entry[1], methods=[]))
        by_shape.setdefault(shape, []).append(entry)
    groups: list[list[tuple[str, ClassInfo, tuple[str, ...]]]] = []
    for shape in sorted(by_shape):
        bucket = by_shape[shape]
        if bucket and not bucket[0][1].is_declaration and _has_method_superset(bucket):
            groups.append(bucket)
        else:
            groups.extend(_exact_definition_groups(bucket))
    return groups


def _has_method_superset(entries: list[tuple[str, ClassInfo, tuple[str, ...]]]) -> bool:
    signatures = [_method_signatures(info) for _, info, _ in entries]
    return any(all(other <= candidate for other in signatures) for candidate in signatures)


def _method_signatures(info: ClassInfo) -> Counter[str]:
    return Counter(
        sha256_text(json.dumps(_fingerprint_value(method), sort_keys=True, default=str))
        for method in info.methods
    )


def _exact_definition_groups(
    entries: list[tuple[str, ClassInfo, tuple[str, ...]]],
) -> list[list[tuple[str, ClassInfo, tuple[str, ...]]]]:
    grouped: dict[str, list[tuple[str, ClassInfo, tuple[str, ...]]]] = {}
    for entry in entries:
        grouped.setdefault(definition_fingerprint(entry[1]), []).append(entry)
    return [grouped[key] for key in sorted(grouped)]


def _resolve_roots(
    symbols: Iterable[str],
    old_to_new: Mapping[str, str],
    canonical: Mapping[str, ClassInfo],
    indexes: _DefinitionIndexes,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for symbol in symbols:
        candidates = _root_candidates(symbol, indexes, old_to_new, canonical)
        if not candidates:
            raise ValueError(f"Requested symbol root was not resolved: {symbol}")
        result[symbol] = max(candidates, key=lambda name: _richness(canonical[name]))
    return result


def _root_candidates(
    symbol: str,
    indexes: _DefinitionIndexes,
    old_to_new: Mapping[str, str],
    canonical: Mapping[str, ClassInfo],
) -> list[str]:
    exact_names = indexes.by_key.get(symbol, [])
    matching_names = indexes.by_display.get(symbol, [])
    candidates = exact_names or matching_names
    return sorted({old_to_new[name] for name in candidates if old_to_new[name] in canonical})


def _dependency_edges(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    source_infos: Mapping[str, ClassInfo],
    old_to_new: Mapping[str, str],
) -> dict[str, set[str]]:
    extractor = context.hierarchy_builder.dependency_extractor
    indexes = _definition_indexes(class_infos)
    by_offset = _source_offset_index(indexes.by_offset, source_infos, old_to_new)
    return {
        name: _dependencies_for_definition(
            name, info, extractor, class_infos, by_offset, indexes.by_name
        )
        for name, info in class_infos.items()
    }


def _source_offset_index(
    canonical_offsets: Mapping[int, list[str]],
    source_infos: Mapping[str, ClassInfo],
    old_to_new: Mapping[str, str],
) -> dict[int, list[str]]:
    """Keep every source DIE edge after equivalent CU definitions merge."""
    by_offset = {offset: list(keys) for offset, keys in canonical_offsets.items()}
    for source_key, info in source_infos.items():
        canonical_key = old_to_new.get(source_key)
        if info.die_offset is None or canonical_key is None:
            continue
        candidates = by_offset.setdefault(info.die_offset, [])
        if canonical_key not in candidates:
            candidates.append(canonical_key)
    return by_offset


def _definition_indexes(
    class_infos: Mapping[str, ClassInfo],
) -> _DefinitionIndexes:
    by_offset: dict[int, list[str]] = {}
    by_name: dict[str, list[str]] = {}
    by_key: dict[str, list[str]] = {}
    by_display: dict[str, list[str]] = {}
    for key, info in class_infos.items():
        by_key.setdefault(key, []).append(key)
        if info.die_offset is not None:
            by_offset.setdefault(info.die_offset, []).append(key)
        for value in (info.name, info.qualified_name):
            if value:
                by_display.setdefault(value, []).append(key)
        for value in (key, info.name, info.qualified_name):
            if value:
                by_name.setdefault(value, []).append(key)
    return _DefinitionIndexes(by_offset, by_name, by_key, by_display)


def _dependencies_for_definition(
    name: str,
    info: ClassInfo,
    extractor: DependencyExtractor,
    class_infos: Mapping[str, ClassInfo],
    by_offset: Mapping[int, list[str]],
    by_name: Mapping[str, list[str]],
) -> set[str]:
    dependencies: set[str] = set()
    offsets = extractor.extract_dependencies(info, include_method_signatures=True)
    for offset in sorted(offsets):
        dependency = _select_candidate(
            by_offset.get(offset, []),
            extractor.get_type_name(offset),
            class_infos,
            by_name,
        )
        if dependency is not None and dependency != name:
            dependencies.add(dependency)
    for base_name in info.base_classes:
        dependency = _select_named_candidate(base_name, class_infos, by_name)
        if dependency is not None and dependency != name:
            dependencies.add(dependency)
    return dependencies


def _select_candidate(
    candidates: list[str],
    type_name: object,
    class_infos: Mapping[str, ClassInfo],
    by_name: Mapping[str, list[str]],
) -> str | None:
    if not candidates:
        normalized = _normalized_type_name(type_name)
        return _select_named_candidate(normalized, class_infos, by_name)
    normalized = _normalized_type_name(type_name)
    matching = [
        candidate
        for candidate in candidates
        if _matches_name(class_infos[candidate], candidate, normalized)
    ]
    return max(matching or candidates, key=lambda name: _richness(class_infos[name]))


def _select_named_candidate(
    value: object,
    class_infos: Mapping[str, ClassInfo],
    by_name: Mapping[str, list[str]],
) -> str | None:
    lookup_name = (
        HeaderTypePlanningService._lookup_type_name(value) if isinstance(value, str) else ""
    )
    normalized = _normalized_type_name(value)
    raw = value if isinstance(value, str) else ""
    candidates = by_name.get(raw, []) or by_name.get(lookup_name, []) or by_name.get(normalized, [])
    if not candidates and "::" in normalized:
        candidates = by_name.get(normalized.rsplit("::", 1)[-1], [])
    return max(candidates, key=lambda name: _richness(class_infos[name])) if candidates else None


def _normalized_type_name(value: object) -> str:
    return HeaderTypePlanningService._normalize_type_name(value) if isinstance(value, str) else ""


def _matches_name(info: ClassInfo, key: str, normalized: str) -> bool:
    names = {key, info.name, info.qualified_name or ""}
    lookup_names = {HeaderTypePlanningService._lookup_type_name(name) for name in names if name}
    if normalized in lookup_names:
        return True
    return normalized in {
        HeaderTypePlanningService._normalize_type_name(name) for name in names if name
    }


def _reachable_origins(
    roots: Mapping[str, str], dependencies: Mapping[str, set[str]]
) -> dict[str, set[str]]:
    origins: dict[str, set[str]] = {name: set() for name in dependencies}
    for root, root_key in roots.items():
        if root_key not in origins:
            continue
        queue: deque[str] = deque([root_key])
        origins[root_key].add(root)
        while queue:
            current = queue.popleft()
            for dependency in sorted(dependencies.get(current, ())):
                if root in origins[dependency]:
                    continue
                origins[dependency].add(root)
                queue.append(dependency)
    return origins


def _embedded_definition_keys(class_infos: Mapping[str, ClassInfo]) -> set[str]:
    """Return separately queried DIEs already rendered inside an owning class."""
    by_identity = {definition_identity(info): name for name, info in class_infos.items()}
    embedded: set[str] = {
        name for name, info in class_infos.items() if info.containing_type is not None
    }
    for info in class_infos.values():
        for nested in _nested_class_infos(info):
            key = by_identity.get(definition_identity(nested))
            if key is not None:
                embedded.add(key)
    return embedded


def _nested_class_infos(info: ClassInfo) -> Iterable[ClassInfo]:
    for nested in info.nested_classes:
        yield nested
        yield from _nested_class_infos(nested)


def _canonical_order(
    order: Iterable[str], old_to_new: Mapping[str, str], reachable: set[str]
) -> list[str]:
    result: list[str] = []
    for name in order:
        canonical = old_to_new.get(name, name)
        if canonical in reachable and canonical not in result:
            result.append(canonical)
    result.extend(name for name in sorted(reachable) if name not in result)
    return result


def definition_identity(info: ClassInfo) -> tuple[object, ...]:
    """Return stable source identity for one parsed definition."""
    return (info.qualified_name or info.name, info.cu_offset, info.die_offset)


def identity_key_for(info: ClassInfo) -> str:
    """Return a collision-free dictionary key for one definition identity."""
    return identity_text(info)


def identity_text(info: ClassInfo) -> str:
    return "|".join(
        (
            info.qualified_name or info.name,
            "none" if info.cu_offset is None else str(info.cu_offset),
            "none" if info.die_offset is None else str(info.die_offset),
        )
    )


def definition_fingerprint(info: ClassInfo) -> str:
    """Hash C++-observable fields while excluding source/provenance metadata."""
    return sha256_text(json.dumps(_fingerprint_value(info), sort_keys=True, default=str))


def _fingerprint_value(value: Any) -> Any:
    if is_dataclass(value):
        excluded = {
            "base_class_offsets",
            "containing_type",
            "cu_offset",
            "declared_return_type_offset",
            "declared_type_offset",
            "die_offset",
            "declaration_file",
            "declaration_line",
            "packing_info",
            "diagnostics",
            "linkage_name",
            "owner_die_offset",
            "return_type_offset",
            "type_offset",
            "source_aliases",
        }
        return {
            field.name: _fingerprint_value(getattr(value, field.name))
            for field in fields(value)
            if field.name not in excluded
        }
    if isinstance(value, Mapping):
        return {str(key): _fingerprint_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_fingerprint_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_fingerprint_value(item) for item in sorted(value, key=lambda item: repr(item))]
    return value


def _richness(info: ClassInfo) -> tuple[int, int, int, int, int, int]:
    return (
        int(not info.is_declaration),
        len(info.members) + 2 * len(info.methods),
        len(info.nested_classes) + len(info.nested_structs) + len(info.unions),
        info.byte_size,
        -(info.cu_offset or 0),
        -(info.die_offset or 0),
    )


__all__ = [
    "CanonicalDefinitionGraph",
    "build_canonical_definition_graph",
    "definition_fingerprint",
    "definition_identity",
    "identity_key_for",
    "identity_text",
]

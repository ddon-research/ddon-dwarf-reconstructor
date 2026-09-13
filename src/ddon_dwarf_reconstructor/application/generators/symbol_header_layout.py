"""Path, ownership-name, and include planning for symbol headers."""

from __future__ import annotations

import os
import posixpath
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from ...core.content_hash import sha256_text
from ...domain.models.dwarf import ClassInfo

_SHARED_OWNER = "shared"


def allocate_header_paths(
    groups: Mapping[tuple[str, str, str], tuple[str, ...]],
    class_infos: Mapping[str, ClassInfo],
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Allocate deterministic flat paths, including cross-owner collisions."""
    conflicting_names = _conflicting_definition_names(groups, class_infos)
    candidates: dict[tuple[str, str], list[tuple[str, tuple[str, ...]]]] = {}
    for (owner, source, _token), group in groups.items():
        candidate = _header_filename(source)
        candidates.setdefault((owner, candidate), []).append((source, group))

    paths: dict[str, tuple[str, tuple[str, ...]]] = {}
    for (owner, candidate), entries in sorted(candidates.items()):
        for _source, group in sorted(entries):
            filename = candidate
            if len(entries) > 1 or _group_has_conflict(group, class_infos, conflicting_names):
                identity = "|".join(class_identity(class_infos[name]) for name in group)
                filename = f"{Path(candidate).stem}-{sha256_text(identity)[:8]}.h"
            relative = (Path(_owner_directory(owner)) / filename).as_posix()
            if relative in paths:
                raise ValueError(f"Conflicting symbol header path: {relative}")
            paths[relative] = (owner, group)
    return paths


def header_names_for_group(
    class_infos: Mapping[str, ClassInfo],
    group: tuple[str, ...],
    class_paths: Mapping[str, str],
    current_directory: str,
) -> dict[str, str]:
    """Exclude alternate definitions of local C++ names from dependency includes."""
    local_display_names = {
        class_infos[name].qualified_name or class_infos[name].name for name in group
    }
    return {
        name: _relative_include(current_directory, dependency_path)
        for name, dependency_path in class_paths.items()
        if name in group
        or (class_infos[name].qualified_name or class_infos[name].name) not in local_display_names
    }


def class_identity(info: ClassInfo) -> str:
    """Return the stable qualified-name/CU/DIE identity used in artifact names."""
    return "|".join((info.qualified_name or info.name, str(info.cu_offset), str(info.die_offset)))


def conflicting_display_names(
    names: Iterable[str], class_infos: Mapping[str, ClassInfo]
) -> set[str]:
    by_display: dict[str, set[str]] = {}
    for name in names:
        info = class_infos[name]
        by_display.setdefault(info.qualified_name or info.name, set()).add(name)
    return {display_name for display_name, identities in by_display.items() if len(identities) > 1}


def _conflicting_definition_names(
    groups: Mapping[tuple[str, str, str], tuple[str, ...]],
    class_infos: Mapping[str, ClassInfo],
) -> set[str]:
    names = (name for group in groups.values() for name in group)
    return conflicting_display_names(names, class_infos)


def _group_has_conflict(
    group: tuple[str, ...],
    class_infos: Mapping[str, ClassInfo],
    conflicting_names: set[str],
) -> bool:
    return any(
        (class_infos[name].qualified_name or class_infos[name].name) in conflicting_names
        for name in group
    )


def _relative_include(current_directory: str, target: str) -> str:
    start = current_directory or "."
    return posixpath.relpath(target, start=start)


def _owner_directory(owner: str) -> str:
    return _SHARED_OWNER if owner == _SHARED_OWNER else _safe_component(owner)


def _header_filename(source: str) -> str:
    filename = os.path.basename(source) if source else "UncategorizedDefinitions.h"
    if not filename.endswith(".h"):
        filename = filename.rsplit(".", 1)[0] + ".h"
    return _safe_component(filename)


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-") or "definition"


def header_groups(
    class_infos: Mapping[str, ClassInfo], owners: Mapping[str, str]
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    grouped = _classes_by_owner_and_source(class_infos, owners)
    conflicting_names = conflicting_display_names(class_infos, class_infos)
    groups: dict[tuple[str, str, str], tuple[str, ...]] = {}
    for (owner, source), names in sorted(grouped.items()):
        groups.update(_groups_for_source(owner, source, names, class_infos, conflicting_names))
    return {key: values for key, values in sorted(groups.items())}


def _classes_by_owner_and_source(
    class_infos: Mapping[str, ClassInfo], owners: Mapping[str, str]
) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for name, info in class_infos.items():
        source = (
            f"{info.name}.h"
            if info.kind == "namespace"
            else info.declaration_file or "UncategorizedDefinitions"
        )
        grouped.setdefault((owners.get(name, _SHARED_OWNER), source), []).append(name)
    return grouped


def _groups_for_source(
    owner: str,
    source: str,
    names: list[str],
    class_infos: Mapping[str, ClassInfo],
    globally_conflicting_names: set[str] | frozenset[str] = frozenset(),
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    by_display: dict[str, list[str]] = {}
    for name in names:
        info = class_infos[name]
        by_display.setdefault(info.qualified_name or info.name, []).append(name)
    local_conflicting_names = {
        display_name for display_name, candidates in by_display.items() if len(candidates) > 1
    }
    conflicting_names = local_conflicting_names | set(globally_conflicting_names)
    conflicting = {
        name
        for name in names
        if (class_infos[name].qualified_name or class_infos[name].name) in conflicting_names
    }
    groups: dict[tuple[str, str, str], tuple[str, ...]] = {}
    regular = sorted(set(names) - conflicting)
    if regular:
        groups[(owner, source, "")] = tuple(regular)
    for name in sorted(conflicting):
        groups[(owner, source, class_identity(class_infos[name]))] = (name,)
    return groups


def guard_suffix(path: str) -> str:
    """Keep include guards unique when different headers share a target name."""
    return f"_{sha256_text(path)[:12].upper()}_H"

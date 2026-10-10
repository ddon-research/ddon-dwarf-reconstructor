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
    local_paths = {class_paths[name] for name in group if name in class_paths}
    local_display_names = {
        class_infos[name].qualified_name or class_infos[name].name for name in group
    }
    return {
        name: _relative_include(current_directory, dependency_path)
        for name, dependency_path in class_paths.items()
        if dependency_path not in local_paths
        and (class_infos[name].qualified_name or class_infos[name].name) not in local_display_names
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
    family_sources = _family_sources(class_infos)
    for name, info in class_infos.items():
        source = (
            f"{info.name}.h"
            if info.kind == "namespace"
            else info.declaration_file or "UncategorizedDefinitions"
        )
        if info.template_rendering is not None:
            source = family_sources[info.template_rendering.primary]
        grouped.setdefault((owners.get(name, _SHARED_OWNER), source), []).append(name)
    return grouped


def _family_sources(infos: Mapping[str, ClassInfo]) -> dict[str, str]:
    sources: dict[str, set[str]] = {}
    for info in infos.values():
        plan = info.template_rendering
        if plan is not None:
            sources.setdefault(plan.primary, set()).add(
                info.declaration_file or "UncategorizedDefinitions"
            )
    return {primary: min(values) for primary, values in sources.items()}


def _groups_for_source(
    owner: str,
    source: str,
    names: list[str],
    class_infos: Mapping[str, ClassInfo],
    globally_conflicting_names: set[str] | frozenset[str] = frozenset(),
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    # Namespace DIEs are output by the dedicated namespace renderer.  A
    # producer can place the namespace DIE and its sibling aggregates in the
    # same source file; keep that root in its own group so the ordinary class
    # renderer never receives a ``kind == namespace`` entry.
    namespace_names = [name for name in names if class_infos[name].kind == "namespace"]
    groups = _namespace_groups(owner, source, namespace_names, class_infos)
    names = [name for name in names if class_infos[name].kind != "namespace"]
    groups.update(_regular_groups(owner, source, names, class_infos, globally_conflicting_names))
    return groups


def _regular_groups(
    owner: str,
    source: str,
    names: list[str],
    class_infos: Mapping[str, ClassInfo],
    globally_conflicting_names: set[str] | frozenset[str],
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    groups: dict[tuple[str, str, str], tuple[str, ...]] = {}
    by_display: dict[str, list[str]] = {}
    for name in names:
        info = class_infos[name]
        by_display.setdefault(info.qualified_name or info.name, []).append(name)
    local_conflicting_names = {
        display_name for display_name, candidates in by_display.items() if len(candidates) > 1
    }
    conflicting_names = local_conflicting_names | set(globally_conflicting_names)
    conflicting = {
        name for name in names if _is_unplanned_conflict(class_infos[name], conflicting_names)
    }
    regular = sorted(set(names) - conflicting)
    if regular:
        groups[(owner, source, "")] = tuple(regular)
    for name in sorted(conflicting):
        groups[(owner, source, class_identity(class_infos[name]))] = (name,)
    return groups


def _namespace_groups(
    owner: str,
    source: str,
    names: Iterable[str],
    class_infos: Mapping[str, ClassInfo],
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    return {(owner, source, class_identity(class_infos[name])): (name,) for name in sorted(names)}


def guard_suffix(path: str) -> str:
    """Keep include guards unique when different headers share a target name."""
    return f"_{sha256_text(path)[:12].upper()}_H"


def _is_unplanned_conflict(info: ClassInfo, conflicting_names: set[str]) -> bool:
    return (
        info.template_rendering is None and (info.qualified_name or info.name) in conflicting_names
    )

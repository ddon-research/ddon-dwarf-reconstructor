"""Reusable dependency and name indexes for one header-generation request."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...models.dwarf import ClassInfo
from .header_cycles import strongly_connected_components

if TYPE_CHECKING:
    from .rendering.operations import HeaderRenderingHost


@dataclass(frozen=True, slots=True)
class HeaderNameIndex(Mapping[str, str]):
    """Name lookup plus precomputed primary-template specialization candidates."""

    _values: Mapping[str, str]
    specializations: Mapping[str, tuple[str, ...]]
    ambiguous: Mapping[str, tuple[str, ...]]

    def __getitem__(self, key: str) -> str:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _collect_specialization_candidates(values: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    specializations: dict[str, set[str]] = {}
    for value, key in values.items():
        if "<" not in value:
            continue
        primary = value.split("<", 1)[0].strip()
        if primary:
            specializations.setdefault(primary, set()).add(key)
    return {primary: tuple(sorted(candidates)) for primary, candidates in specializations.items()}


def _record_name(values: dict[str, set[str]], spelling: str, key: str) -> None:
    values.setdefault(spelling, set()).add(key)


def _index_template_primary(class_info: ClassInfo, key: str, values: dict[str, set[str]]) -> None:
    from .header_type_planning import HeaderTypePlanningService

    plan = class_info.template_rendering
    if plan is not None and plan.mode == "generic" and plan.representative and plan.primary:
        for cand in (plan.primary, plan.primary.split("::")[-1]):
            _record_name(values, cand, key)
            _record_name(values, HeaderTypePlanningService._normalize_type_name(cand), key)


def _index_class_names(class_info: ClassInfo, key: str, values: dict[str, set[str]]) -> None:
    from .header_type_planning import HeaderTypePlanningService

    for value in (key, class_info.name, class_info.qualified_name):
        if value:
            _record_name(values, value, key)
            _record_name(values, HeaderTypePlanningService._normalize_type_name(value), key)
    for nested in HeaderTypePlanningService._iter_nested_classes(class_info):
        for value in (nested.qualified_name, f"{class_info.name}::{nested.name}"):
            if value:
                _record_name(values, value, key)
                _record_name(values, HeaderTypePlanningService._normalize_type_name(value), key)
    _index_template_primary(class_info, key, values)


def build_header_name_index(class_infos: Mapping[str, ClassInfo]) -> HeaderNameIndex:
    """Build deterministic direct and primary-template name indexes once."""
    candidates: dict[str, set[str]] = {}
    for key, class_info in class_infos.items():
        _index_class_names(class_info, key, candidates)
    values = {name: next(iter(keys)) for name, keys in candidates.items() if len(keys) == 1}
    ambiguous = {name: tuple(sorted(keys)) for name, keys in candidates.items() if len(keys) > 1}

    return HeaderNameIndex(
        MappingProxyType(values),
        MappingProxyType(_collect_specialization_candidates(values)),
        MappingProxyType(ambiguous),
    )


def _freeze_dependencies(
    dependencies: Mapping[str, Sequence[str] | set[str] | frozenset[str]],
) -> Mapping[str, frozenset[str]]:
    return MappingProxyType(
        {name: frozenset(sorted(required)) for name, required in sorted(dependencies.items())}
    )


@dataclass(frozen=True, slots=True)
class HeaderDependencyPlan:
    """Immutable dependency results shared by rendering and diagnostics."""

    dependencies: Mapping[str, frozenset[str]]
    top_level_dependencies: Mapping[str, frozenset[str]]
    name_index: HeaderNameIndex
    owner_dependencies: Mapping[str, frozenset[str]]
    unschedulable_owner_cycles: tuple[tuple[str, ...], ...]
    ambiguous_base_requirements: tuple[str, ...] = ()


def _schedule_owner_dependencies(
    definitions: Mapping[str, set[str]], owners: Mapping[str, set[str]]
) -> tuple[dict[str, set[str]], tuple[tuple[str, ...], ...]]:
    """Withhold owner includes inside SCCs until a legal co-location plan exists."""
    combined = {
        name: set(required) | owners.get(name, set()) for name, required in definitions.items()
    }
    components = strongly_connected_components(combined)
    blocked = tuple(
        component
        for component in components
        if any(target in component for name in component for target in owners.get(name, ()))
    )
    for component in blocked:
        members = set(component)
        for name in component:
            combined[name].difference_update(owners.get(name, set()) & members)
    return combined, blocked


class HeaderDependencyPlanService:
    """Build one plan and apply it to many output-group include requests."""

    def build_dependency_plan(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        hierarchy_order: Sequence[str],
        typedefs: Mapping[str, str] | None = None,
    ) -> HeaderDependencyPlan:
        """Build full and top-level dependency maps with shared name indexes."""
        from .header_dependency_ambiguity import ambiguous_base_requirements
        from .header_dependency_names import _offset_name_index, _owner_dependencies_for_class
        from .template_declarations import project_template

        infos = {key: project_template(info) for key, info in class_infos.items()}
        typedef_map = dict(typedefs) if typedefs is not None else None
        name_index = build_header_name_index(infos)
        definitions = self._definition_dependencies(infos, typedef_map, name_index=name_index)
        offset_names = _offset_name_index(infos)
        owners = {
            name: _owner_dependencies_for_class(info, name_index, offset_names) - {name}
            for name, info in infos.items()
        }
        dependencies, owner_cycles = _schedule_owner_dependencies(definitions, owners)
        top_level_infos = self._top_level_infos(infos, list(hierarchy_order))
        top_level_dependencies = self._definition_dependencies(
            top_level_infos, typedef_map, name_index=name_index
        )
        for name in top_level_dependencies:
            top_level_dependencies[name].update(dependencies[name] & top_level_infos.keys())
        return HeaderDependencyPlan(
            _freeze_dependencies(dependencies),
            _freeze_dependencies(top_level_dependencies),
            name_index,
            _freeze_dependencies(owners),
            owner_cycles,
            ambiguous_base_requirements(infos, name_index.ambiguous, offset_names),
        )

    def external_dependency_headers_for_group_specs(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        groups: Mapping[str, set[str]],
        header_names_by_group: Mapping[str, Mapping[str, str]],
        typedefs_by_group: Mapping[str, Mapping[str, str]] | None = None,
        *,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> dict[str, dict[str, str]]:
        """Resolve many groups using one plan and group-local include maps."""
        plan = dependency_plan or self.build_dependency_plan(class_infos, ())
        result: dict[str, dict[str, str]] = {}
        for group_id, rendered_names in sorted(groups.items()):
            result[group_id] = self._dependency_headers_for_group(
                class_infos,
                rendered_names,
                header_names_by_group.get(group_id, {}),
                (typedefs_by_group or {}).get(group_id, {}),
                plan,
            )
        return result

    def _dependency_headers_for_group(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        rendered_names: set[str],
        header_names: Mapping[str, str],
        group_typedefs: Mapping[str, str],
        plan: HeaderDependencyPlan,
    ) -> dict[str, str]:
        current_headers = {header_names[name] for name in rendered_names if name in header_names}
        dependencies = self._dependencies_for_group(
            class_infos, rendered_names, group_typedefs, plan
        )
        required_names = self._required_dependency_names(
            rendered_names, dependencies, header_names, current_headers
        )
        required_names.update(
            self._required_typedef_dependency_names(
                class_infos,
                rendered_names,
                group_typedefs,
                header_names,
                current_headers,
                name_index=plan.name_index,
            )
        )
        return {name: header_names[name] for name in sorted(required_names) if name in header_names}

    def _dependencies_for_group(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        rendered_names: set[str],
        group_typedefs: Mapping[str, str],
        plan: HeaderDependencyPlan,
    ) -> Mapping[str, set[str] | frozenset[str]]:
        if not group_typedefs:
            return plan.dependencies
        group_dependencies = {name: set(plan.dependencies.get(name, ())) for name in rendered_names}
        local_infos = {name: class_infos[name] for name in rendered_names if name in class_infos}
        self._add_typedef_dependencies(
            local_infos,
            group_typedefs,
            plan.name_index,
            group_dependencies,
        )
        return group_dependencies


__all__ = [
    "HeaderDependencyPlan",
    "HeaderDependencyPlanService",
    "HeaderNameIndex",
    "build_header_name_index",
]

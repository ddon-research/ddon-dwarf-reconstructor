"""Reusable dependency and name indexes for one header-generation request."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...models.dwarf import ClassInfo

if TYPE_CHECKING:
    from .rendering.operations import HeaderRenderingHost


@dataclass(frozen=True, slots=True)
class HeaderNameIndex(Mapping[str, str]):
    """Name lookup plus precomputed primary-template specialization candidates."""

    _values: Mapping[str, str]
    specializations: Mapping[str, tuple[str, ...]]

    def __getitem__(self, key: str) -> str:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def build_header_name_index(class_infos: Mapping[str, ClassInfo]) -> HeaderNameIndex:
    """Build deterministic direct and primary-template name indexes once."""
    # Import lazily: ``header_type_planning`` imports the rendering package,
    # whose public facade imports this module.  Keeping the policy dependency
    # at the call boundary avoids a package-initialization cycle.
    from .header_type_planning import HeaderTypePlanningService

    values: dict[str, str] = {}
    for key, class_info in class_infos.items():
        for value in (key, class_info.name, class_info.qualified_name):
            if not value:
                continue
            values.setdefault(value, key)
            values.setdefault(HeaderTypePlanningService._normalize_type_name(value), key)

    specializations: dict[str, set[str]] = {}
    for value, key in values.items():
        if "<" not in value:
            continue
        primary = value.split("<", 1)[0].strip()
        if primary:
            specializations.setdefault(primary, set()).add(key)
    return HeaderNameIndex(
        MappingProxyType(values),
        MappingProxyType(
            {primary: tuple(sorted(candidates)) for primary, candidates in specializations.items()}
        ),
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


class HeaderDependencyPlanService:
    """Build one plan and apply it to many output-group include requests."""

    def build_dependency_plan(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        hierarchy_order: Sequence[str],
        typedefs: Mapping[str, str] | None = None,
    ) -> HeaderDependencyPlan:
        """Build full and top-level dependency maps with shared name indexes."""
        from .template_declarations import project_template

        infos = {key: project_template(info) for key, info in class_infos.items()}
        typedef_map = dict(typedefs) if typedefs is not None else None
        name_index = build_header_name_index(infos)
        dependencies = self._definition_dependencies(infos, typedef_map, name_index=name_index)
        top_level_infos = self._top_level_infos(infos, list(hierarchy_order))
        top_level_dependencies = self._definition_dependencies(
            top_level_infos, typedef_map, name_index=name_index
        )
        return HeaderDependencyPlan(
            _freeze_dependencies(dependencies),
            _freeze_dependencies(top_level_dependencies),
            name_index,
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

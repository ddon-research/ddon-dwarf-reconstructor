"""Header ordering operations."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Mapping

from ....core.observability import get_logger, log_event
from ...models.dwarf import ClassInfo, MemberInfo
from .header_cycles import cycle_fallback_name, strongly_connected_components
from .header_dependency_names import (
    _base_offset_dependencies,
    _nested_names,
    _offset_name_index,
    _requires_complete_method_signature,
    _resolve_class_name,
    _type_offset_key,
)
from .header_dependency_plan import HeaderDependencyPlan, HeaderNameIndex, build_header_name_index
from .header_type_planning import HeaderTypePlanningService
from .rendering.operations import HeaderRenderingHost

logger = get_logger(__name__)


def _class_name_index(class_infos: Mapping[str, ClassInfo]) -> HeaderNameIndex:
    """Map rendered C++ names to canonical keys and specialization candidates."""
    return build_header_name_index(class_infos)


class HeaderOrderingService:
    def _order_class_definitions(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None = None,
        allow_cyclic_dependencies: bool = False,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> list[str]:
        """Order definitions so inheritance and by-value edges precede their users."""
        if dependency_plan is None:
            top_level_infos = self._top_level_infos(class_infos, hierarchy_order)
            dependencies = self._definition_dependencies(top_level_infos, typedefs)
        else:
            top_level_names = self._top_level_infos(class_infos, hierarchy_order)
            dependencies = {
                name: {
                    dependency
                    for dependency in dependency_plan.top_level_dependencies.get(name, ())
                    if dependency in class_infos
                }
                for name in top_level_names
            }
            if typedefs:
                self._add_typedef_dependencies(
                    class_infos, typedefs, dependency_plan.name_index, dependencies
                )
        return self._stable_topological_order(
            dependencies, hierarchy_order, allow_cycles=allow_cyclic_dependencies
        )

    def _top_level_infos(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
    ) -> dict[str, ClassInfo]:
        nested_names = {
            nested_name
            for class_info in class_infos.values()
            for nested_name in _nested_names(class_info)
        }
        hierarchy_names = set(hierarchy_order)
        return {
            name: class_info
            for name, class_info in class_infos.items()
            if class_info.containing_type is None
            and (
                name in hierarchy_names
                or (name not in nested_names and class_info.name not in nested_names)
            )
        }

    def _definition_dependencies(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str] | None = None,
        *,
        name_index: Mapping[str, str] | None = None,
    ) -> dict[str, set[str]]:
        name_index = _class_name_index(class_infos) if name_index is None else name_index
        offset_names = _offset_name_index(class_infos)
        dependencies: dict[str, set[str]] = {name: set() for name in class_infos}
        for class_name, class_info in class_infos.items():
            if (
                class_info.template_rendering is not None
                and class_info.template_rendering.mode == "generic"
                and not class_info.template_rendering.representative
            ):
                continue
            self._add_class_dependencies(
                class_name, class_info, name_index, dependencies, offset_names
            )
        if typedefs:
            self._add_typedef_dependencies(class_infos, typedefs, name_index, dependencies)
        return dependencies

    def _add_class_dependencies(
        self: HeaderRenderingHost,
        class_name: str,
        class_info: ClassInfo,
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
        offset_names: dict[tuple[int | None, int], str],
    ) -> None:
        self._add_base_dependencies(class_name, class_info, name_index, dependencies, offset_names)
        self._add_member_dependencies(
            class_name, class_info.members, name_index, dependencies, offset_names
        )
        self._add_nested_aggregate_dependencies(
            class_name, class_info, name_index, dependencies, offset_names
        )
        self._add_method_dependencies(
            class_name, class_info, name_index, dependencies, offset_names
        )
        for nested_class in class_info.nested_classes:
            self._add_class_dependencies(
                class_name, nested_class, name_index, dependencies, offset_names
            )

    def cyclic_dependency_components(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None = None,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        """Return deterministic strongly connected by-value definition groups."""
        if dependency_plan is not None:
            dependencies = {
                name: set(required)
                for name, required in dependency_plan.top_level_dependencies.items()
            }
            return strongly_connected_components(dependencies)
        top_level_infos = self._top_level_infos(class_infos, hierarchy_order)
        dependencies = self._definition_dependencies(top_level_infos, typedefs)
        return strongly_connected_components(dependencies)

    def _add_typedef_dependencies(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str],
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
    ) -> None:
        """Resolve by-value aliases whose terminal DIE is not in the text type."""
        for class_name, class_info in class_infos.items():
            for member in self._all_nested_members(class_info):
                if member.is_static or self._is_indirection_type(member.type_name):
                    continue
                alias = self._normalize_type_name(member.type_name).split("[", 1)[0].strip()
                if alias not in typedefs:
                    continue
                underlying = typedefs[alias]
                dependencies[class_name].update(
                    referenced
                    for referenced in self._referenced_dependency_names(underlying, name_index)
                    if referenced != class_name
                )

    def _add_nested_aggregate_dependencies(
        self: HeaderRenderingHost,
        class_name: str,
        class_info: ClassInfo,
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
        offset_names: dict[tuple[int | None, int], str] | None = None,
    ) -> None:
        """Track by-value types used by nested structs and unions."""
        nested_members = [
            member
            for nested_struct in class_info.nested_structs
            for member in nested_struct.members
        ]
        nested_members.extend(member for union in class_info.unions for member in union.members)
        nested_members.extend(
            member
            for union in class_info.unions
            for nested_struct in union.nested_structs
            for member in nested_struct.members
        )
        self._add_member_dependencies(
            class_name, nested_members, name_index, dependencies, offset_names
        )

    def external_dependency_headers(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Return headers needed by definitions rendered in another file."""
        plan = self.build_dependency_plan(class_infos, (), typedefs)
        name_index = plan.name_index
        dependencies = plan.dependencies
        current_headers = {
            header_names[class_name]
            for class_name in rendered_class_names
            if class_name in header_names
        }
        required_names = self._required_dependency_names(
            rendered_class_names, dependencies, header_names, current_headers
        )
        required_names.update(
            self._required_typedef_dependency_names(
                class_infos,
                rendered_class_names,
                typedefs or {},
                header_names,
                current_headers,
                name_index=name_index,
            )
        )
        return {
            dependency_name: header_names[dependency_name]
            for dependency_name in sorted(required_names)
        }

    def external_dependency_headers_for_groups(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        groups: Mapping[str, set[str]],
        header_names: Mapping[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, dict[str, str]]:
        """Plan external includes for many files after one dependency scan."""
        plan = self.build_dependency_plan(class_infos, (), typedefs)
        name_index = plan.name_index
        dependencies = plan.dependencies
        known_header_names = dict(header_names)
        result: dict[str, dict[str, str]] = {}
        for group_id, rendered_names in sorted(groups.items()):
            current_headers = {
                known_header_names[class_name]
                for class_name in rendered_names
                if class_name in known_header_names
            }
            required_names = self._required_dependency_names(
                rendered_names, dependencies, known_header_names, current_headers
            )
            required_names.update(
                self._required_typedef_dependency_names(
                    class_infos,
                    rendered_names,
                    typedefs or {},
                    known_header_names,
                    current_headers,
                    name_index=name_index,
                )
            )
            result[group_id] = {
                dependency_name: known_header_names[dependency_name]
                for dependency_name in sorted(required_names)
            }
        return result

    @staticmethod
    def _required_dependency_names(
        rendered_class_names: set[str],
        dependencies: Mapping[str, set[str] | frozenset[str]],
        header_names: dict[str, str],
        current_headers: set[str],
    ) -> set[str]:
        return {
            dependency_name
            for class_name in rendered_class_names
            for dependency_name in dependencies.get(class_name, set())
            if dependency_name not in rendered_class_names
            and dependency_name in header_names
            and header_names[dependency_name] not in current_headers
        }

    def _required_typedef_dependency_names(
        self: HeaderRenderingHost,
        class_infos: Mapping[str, ClassInfo],
        rendered_class_names: set[str],
        typedefs: Mapping[str, str],
        header_names: Mapping[str, str],
        current_headers: set[str],
        *,
        name_index: Mapping[str, str] | None = None,
    ) -> set[str]:
        return {
            dependency_name
            for class_name in rendered_class_names
            for underlying_type in self._value_typedef_underlyings(
                self._class_info_for_name(class_infos, class_name), typedefs
            )
            for dependency_name in self._value_typedef_dependency_names(
                underlying_type, class_infos, name_index=name_index
            )
            if dependency_name not in rendered_class_names
            and dependency_name in header_names
            and header_names[dependency_name] not in current_headers
        }

    def _typedef_dependency_names(
        self: HeaderRenderingHost,
        underlying_type: str,
        class_infos: Mapping[str, ClassInfo],
        *,
        name_index: Mapping[str, str] | None = None,
    ) -> set[str]:
        name_index = _class_name_index(class_infos) if name_index is None else name_index
        return self._referenced_dependency_names(underlying_type, name_index)

    @staticmethod
    def _template_specialization_names(expression: str, name_index: Mapping[str, str]) -> set[str]:
        exact = name_index.get(expression)
        if exact is not None:
            return {exact}
        if "<" in expression:
            primary = expression.split("<", 1)[0].strip()
            exact_primary = name_index.get(primary)
            if exact_primary is not None:
                return {exact_primary}
            candidates = getattr(name_index, "specializations", {}).get(primary)
            if candidates:
                return set(candidates)
        return set()

    def _value_typedef_underlyings(
        self: HeaderRenderingHost,
        class_info: ClassInfo | None,
        typedefs: Mapping[str, str],
    ) -> list[str]:
        if class_info is None:
            return []
        return [
            typedefs[alias]
            for member in self._all_nested_members(class_info)
            if not self._is_indirection_type(member.type_name)
            for alias in [self._normalize_type_name(member.type_name).split("[", 1)[0].strip()]
            if alias in typedefs
        ]

    @staticmethod
    def _class_info_for_name(
        class_infos: Mapping[str, ClassInfo], class_name: str
    ) -> ClassInfo | None:
        if class_name in class_infos:
            return class_infos[class_name]
        return next((info for info in class_infos.values() if info.name == class_name), None)

    def _value_typedef_dependency_names(
        self: HeaderRenderingHost,
        underlying_type: str,
        class_infos: Mapping[str, ClassInfo],
        *,
        name_index: Mapping[str, str] | None = None,
    ) -> set[str]:
        name_index = _class_name_index(class_infos) if name_index is None else name_index
        return self._typedef_dependency_names(underlying_type, class_infos, name_index=name_index)

    def _add_base_dependencies(
        self: HeaderRenderingHost,
        class_name: str,
        class_info: ClassInfo,
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
        offset_names: Mapping[tuple[int | None, int], str],
    ) -> None:
        dependencies[class_name].update(
            _base_offset_dependencies(class_info, offset_names) - {class_name}
        )
        for base_name in class_info.base_classes:
            dependency = _resolve_class_name(base_name, name_index)
            if dependency is not None and dependency != class_name:
                dependencies[class_name].add(dependency)
            for expression in self._template_expressions(base_name):
                opening = expression.find("<")
                if opening < 0:
                    continue
                arguments = HeaderTypePlanningService._split_template_arguments(
                    expression[opening + 1 : -1]
                )
                for argument in arguments:
                    dependency = _resolve_class_name(argument, name_index)
                    if dependency is not None and dependency != class_name:
                        dependencies[class_name].add(dependency)

    def _add_member_dependencies(
        self: HeaderRenderingHost,
        class_name: str,
        members: list[MemberInfo],
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
        offset_names: dict[tuple[int | None, int], str] | None = None,
    ) -> None:
        for member in members:
            dependencies[class_name].update(
                self._member_dependency_names(member, class_name, name_index, offset_names)
            )

    def _add_method_dependencies(
        self: HeaderRenderingHost,
        class_name: str,
        class_info: ClassInfo,
        name_index: Mapping[str, str],
        dependencies: dict[str, set[str]],
        offset_names: dict[tuple[int | None, int], str],
    ) -> None:
        """Include complete definitions only for contractually complete signatures."""
        for type_name, type_offset, type_key in self._method_signature_types(class_info):
            if _requires_complete_method_signature(type_name):
                dependencies[class_name].update(
                    self._complete_signature_dependencies(
                        type_name, type_offset, type_key, class_name, name_index, offset_names
                    )
                )

    @staticmethod
    def _method_signature_types(
        class_info: ClassInfo,
    ) -> Iterator[tuple[str, int | None, tuple[int | None, int] | None]]:
        for method in class_info.methods:
            yield (
                method.return_type,
                method.return_type_offset,
                _type_offset_key(
                    method.cu_offset, method.return_type_offset, method.return_type_reference
                ),
            )
            yield from (
                (
                    parameter.type_name,
                    parameter.type_offset,
                    _type_offset_key(
                        parameter.cu_offset, parameter.type_offset, parameter.type_reference
                    ),
                )
                for parameter in method.parameters or ()
            )

    def _complete_signature_dependencies(
        self: HeaderRenderingHost,
        type_name: str,
        type_offset: int | None,
        type_key: tuple[int | None, int] | None,
        class_name: str,
        name_index: Mapping[str, str],
        offset_names: dict[tuple[int | None, int], str],
    ) -> set[str]:
        dependencies = {
            dependency
            for dependency in self._referenced_dependency_names(type_name, name_index)
            if dependency != class_name
        }
        referenced_name = offset_names.get(type_key) if type_key is not None else None
        if referenced_name and referenced_name != class_name:
            dependencies.add(referenced_name)
        return dependencies

    @staticmethod
    def _is_indirection_type(type_name: str) -> bool:
        if "<" in type_name and ">" in type_name:
            outer = re.sub(r"<.*>", "", type_name)
        else:
            outer = type_name
        return "*" in outer or "&" in outer

    def _member_dependency_names(
        self: HeaderRenderingHost,
        member: MemberInfo,
        class_name: str,
        name_index: Mapping[str, str],
        offset_names: dict[tuple[int | None, int], str] | None,
    ) -> set[str]:
        if member.is_static or self._is_indirection_type(member.type_name):
            return set()
        dependencies = {
            referenced_name
            for referenced_name in self._referenced_dependency_names(member.type_name, name_index)
            if referenced_name != class_name
        }
        if member.type_offset is not None and offset_names:
            key = _type_offset_key(member.cu_offset, member.type_offset, member.type_reference)
            referenced_name = offset_names.get(key) if key is not None else None
            if referenced_name and referenced_name != class_name:
                dependencies.add(referenced_name)
        return dependencies

    def _referenced_dependency_names(
        self: HeaderRenderingHost, type_name: str, name_index: Mapping[str, str]
    ) -> set[str]:
        dependencies: set[str] = set()
        referenced_name = _resolve_class_name(type_name, name_index)
        if referenced_name:
            dependencies.add(referenced_name)
        for expression in HeaderTypePlanningService._template_expressions(type_name):
            dependencies.update(self._template_specialization_names(expression, name_index))
            opening = expression.find("<")
            if opening < 0:
                continue
            arguments = HeaderTypePlanningService._split_template_arguments(
                expression[opening + 1 : -1]
            )
            for argument in arguments:
                argument_name = _resolve_class_name(argument, name_index)
                if argument_name:
                    dependencies.add(argument_name)
                # Nested template arguments (for example allocator<vector<T>>)
                # are represented by their own expressions and must contribute
                # their complete by-value dependencies as well.
                dependencies.update(self._referenced_dependency_names(argument, name_index))
        return dependencies


def _ready_names(remaining: dict[str, set[str]], preferred: list[str]) -> list[str]:
    return [name for name in preferred if name in remaining and not remaining[name]]


def _remove_dependency(remaining: dict[str, set[str]], name: str) -> None:
    for required in remaining.values():
        required.discard(name)


def _stable_topological_order(
    dependencies: dict[str, set[str]],
    hierarchy_order: list[str],
    allow_cycles: bool = False,
) -> list[str]:
    ordered: list[str] = []
    remaining = {name: set(required) for name, required in dependencies.items()}
    preferred = [name for name in hierarchy_order if name in remaining]
    preferred.extend(sorted(set(remaining) - set(preferred)))
    while remaining:
        ready = _ready_names(remaining, preferred)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            if not allow_cycles:
                raise ValueError(f"Cannot order cyclic by-value dependencies: {cycle}")
            ready = [cycle_fallback_name(remaining, preferred)]
            log_event(
                logger,
                logging.WARNING,
                "cyclic_by_value_dependency_unschedulable",
                cycle=cycle,
                selected=ready[0],
            )
        for name in ready:
            ordered.append(name)
            del remaining[name]
            _remove_dependency(remaining, name)
    return ordered


HeaderOrderingService._stable_topological_order = staticmethod(_stable_topological_order)
HeaderOrderingService._ready_names = staticmethod(_ready_names)
HeaderOrderingService._remove_dependency = staticmethod(_remove_dependency)

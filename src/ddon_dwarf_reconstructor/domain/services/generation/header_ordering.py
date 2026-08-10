"""Header ordering operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, MemberInfo
from .header_type_planning import HeaderTypePlanningMixin

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HeaderOrderingMixin:
    def _order_class_definitions(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
    ) -> list[str]:
        """Order definitions so inheritance and by-value edges precede their users."""
        top_level_infos = self._top_level_infos(class_infos, hierarchy_order)
        dependencies = self._definition_dependencies(top_level_infos)
        return self._stable_topological_order(dependencies, hierarchy_order)

    def _top_level_infos(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
    ) -> dict[str, ClassInfo]:
        nested_names = {
            nested_name
            for class_info in class_infos.values()
            for nested_name in self._nested_names(class_info)
        }
        hierarchy_names = set(hierarchy_order)
        return {
            name: class_info
            for name, class_info in class_infos.items()
            if name in hierarchy_names
            or (
                class_info.containing_type is None
                and name not in nested_names
                and class_info.name not in nested_names
            )
        }

    @classmethod
    def _nested_names(cls, class_info: ClassInfo) -> set[str]:
        names = {nested.name for nested in HeaderTypePlanningMixin._iter_nested_classes(class_info)}
        names.update(
            nested.qualified_name
            for nested in HeaderTypePlanningMixin._iter_nested_classes(class_info)
            if nested.qualified_name
        )
        return names

    def _definition_dependencies(
        self: HeaderGeneratorContext, class_infos: dict[str, ClassInfo]
    ) -> dict[str, set[str]]:
        names = set(class_infos)
        dependencies: dict[str, set[str]] = {name: set() for name in names}
        for class_name, class_info in class_infos.items():
            self._add_base_dependencies(class_name, class_info, names, dependencies)
            self._add_member_dependencies(class_name, class_info.members, names, dependencies)
            for nested_class in HeaderTypePlanningMixin._iter_nested_classes(class_info):
                self._add_base_dependencies(class_name, nested_class, names, dependencies)
                self._add_member_dependencies(class_name, nested_class.members, names, dependencies)
        return dependencies

    def external_dependency_headers(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
    ) -> dict[str, str]:
        """Return headers needed by definitions rendered in another file."""
        dependencies = self._definition_dependencies(class_infos)
        current_headers = {
            header_names[class_name]
            for class_name in rendered_class_names
            if class_name in header_names
        }
        required_names = {
            dependency_name
            for class_name in rendered_class_names
            for dependency_name in dependencies.get(class_name, set())
            if dependency_name not in rendered_class_names
            and dependency_name in header_names
            and header_names[dependency_name] not in current_headers
        }
        return {
            dependency_name: header_names[dependency_name]
            for dependency_name in sorted(required_names)
        }

    def _add_base_dependencies(
        self: HeaderGeneratorContext,
        class_name: str,
        class_info: ClassInfo,
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None:
        dependencies[class_name].update(
            base_name for base_name in class_info.base_classes if base_name in names
        )

    def _add_member_dependencies(
        self: HeaderGeneratorContext,
        class_name: str,
        members: list[MemberInfo],
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None:
        for member in members:
            if member.is_static or "*" in member.type_name or "&" in member.type_name:
                continue
            referenced_name = self._referenced_class_name(member.type_name, names)
            if referenced_name and referenced_name != class_name:
                dependencies[class_name].add(referenced_name)

    @staticmethod
    def _stable_topological_order(
        dependencies: dict[str, set[str]], hierarchy_order: list[str]
    ) -> list[str]:
        ordered: list[str] = []
        remaining = {name: set(required) for name, required in dependencies.items()}
        preferred = [name for name in hierarchy_order if name in remaining]
        preferred.extend(sorted(set(remaining) - set(preferred)))
        while remaining:
            ready = HeaderOrderingMixin._ready_names(remaining, preferred)
            if not ready:
                cycle = ", ".join(sorted(remaining))
                raise ValueError(f"Cannot order cyclic by-value dependencies: {cycle}")
            for name in ready:
                ordered.append(name)
                del remaining[name]
                HeaderOrderingMixin._remove_dependency(remaining, name)
        return ordered

    @staticmethod
    def _ready_names(remaining: dict[str, set[str]], preferred: list[str]) -> list[str]:
        ready = [name for name in preferred if name in remaining and not remaining[name]]
        return ready

    @staticmethod
    def _remove_dependency(remaining: dict[str, set[str]], name: str) -> None:
        for required in remaining.values():
            required.discard(name)

    @classmethod
    def _collect_resolved_forward_declarations(
        cls,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
    ) -> set[str]:
        """Declare resolved aggregates before methods can reference later definitions."""
        nested_names = cls._nested_definition_names(class_infos)
        hierarchy_names = set(hierarchy_order)
        declarations: set[str] = set()

        for key, class_info in class_infos.items():
            if key not in hierarchy_names and (
                class_info.containing_type is not None or key in nested_names
            ):
                continue
            declaration = cls._forward_declaration(class_info)
            if declaration:
                declarations.add(declaration)

        return declarations

    @classmethod
    def _nested_definition_names(cls, class_infos: dict[str, ClassInfo]) -> set[str]:
        names: set[str] = set()
        for class_info in class_infos.values():
            for nested_class in HeaderTypePlanningMixin._iter_nested_classes(class_info):
                names.add(nested_class.name)
                if nested_class.qualified_name:
                    names.add(nested_class.qualified_name)
        return names

    @staticmethod
    def _forward_declaration(class_info: ClassInfo) -> str | None:
        if not re.fullmatch(r"[A-Za-z_]\w*", class_info.name):
            return None
        kind = class_info.kind if class_info.kind in {"class", "struct", "union"} else "class"
        return f"{kind} {class_info.name};"

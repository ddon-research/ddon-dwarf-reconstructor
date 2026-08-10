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
        typedefs: dict[str, str] | None = None,
    ) -> list[str]:
        """Order definitions so inheritance and by-value edges precede their users."""
        top_level_infos = self._top_level_infos(class_infos, hierarchy_order)
        dependencies = self._definition_dependencies(top_level_infos, typedefs)
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
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, set[str]]:
        names = set(class_infos)
        offset_names = {
            info.die_offset: name
            for name, info in class_infos.items()
            if info.die_offset is not None
        }
        dependencies: dict[str, set[str]] = {name: set() for name in names}
        for class_name, class_info in class_infos.items():
            self._add_base_dependencies(class_name, class_info, names, dependencies)
            self._add_member_dependencies(
                class_name, class_info.members, names, dependencies, offset_names
            )
            self._add_nested_aggregate_dependencies(
                class_name, class_info, names, dependencies, offset_names
            )
            for nested_class in HeaderTypePlanningMixin._iter_nested_classes(class_info):
                self._add_base_dependencies(class_name, nested_class, names, dependencies)
                self._add_member_dependencies(
                    class_name, nested_class.members, names, dependencies, offset_names
                )
        if typedefs:
            self._add_typedef_dependencies(class_infos, typedefs, names, dependencies)
        return dependencies

    def _add_typedef_dependencies(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str],
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None:
        """Resolve by-value aliases whose terminal DIE is not in the text type."""
        for class_name, class_info in class_infos.items():
            for member in self._all_nested_members(class_info):
                if member.is_static or "*" in member.type_name or "&" in member.type_name:
                    continue
                alias = self._normalize_type_name(member.type_name).split("[", 1)[0].strip()
                if alias not in typedefs:
                    continue
                referenced = self._referenced_class_name(typedefs[alias], names)
                if referenced and referenced != class_name:
                    dependencies[class_name].add(referenced)

    def _add_nested_aggregate_dependencies(
        self: HeaderGeneratorContext,
        class_name: str,
        class_info: ClassInfo,
        names: set[str],
        dependencies: dict[str, set[str]],
        offset_names: dict[int, str] | None = None,
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
        self._add_member_dependencies(class_name, nested_members, names, dependencies, offset_names)

    def external_dependency_headers(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Return headers needed by definitions rendered in another file."""
        dependencies = self._definition_dependencies(class_infos, typedefs)
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
                class_infos, rendered_class_names, typedefs or {}, header_names, current_headers
            )
        )
        return {
            dependency_name: header_names[dependency_name]
            for dependency_name in sorted(required_names)
        }

    @staticmethod
    def _required_dependency_names(
        rendered_class_names: set[str],
        dependencies: dict[str, set[str]],
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
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        typedefs: dict[str, str],
        header_names: dict[str, str],
        current_headers: set[str],
    ) -> set[str]:
        return {
            dependency_name
            for class_name in rendered_class_names
            for underlying_type in self._value_typedef_underlyings(
                self._class_info_for_name(class_infos, class_name), typedefs
            )
            for dependency_name in self._value_typedef_dependency_names(
                underlying_type, class_infos
            )
            if dependency_name not in rendered_class_names
            and dependency_name in header_names
            and header_names[dependency_name] not in current_headers
        }

    def _typedef_dependency_names(
        self: HeaderGeneratorContext,
        underlying_type: str,
        class_infos: dict[str, ClassInfo],
    ) -> set[str]:
        names = set(class_infos)
        names.update(info.name for info in class_infos.values())
        dependencies: set[str] = set()
        for expression in self._template_expressions(underlying_type):
            dependencies.update(self._template_specialization_names(expression, names))
        return dependencies

    @staticmethod
    def _template_specialization_names(expression: str, names: set[str]) -> set[str]:
        primary = expression.split("<", 1)[0].strip()
        return {name for name in names if name == primary or name.startswith(f"{primary}<")}

    def _value_typedef_underlyings(
        self: HeaderGeneratorContext,
        class_info: ClassInfo | None,
        typedefs: dict[str, str],
    ) -> list[str]:
        if class_info is None:
            return []
        return [
            typedefs[alias]
            for member in self._all_nested_members(class_info)
            if "*" not in member.type_name and "&" not in member.type_name
            for alias in [self._normalize_type_name(member.type_name).split("[", 1)[0].strip()]
            if alias in typedefs
        ]

    @staticmethod
    def _class_info_for_name(
        class_infos: dict[str, ClassInfo], class_name: str
    ) -> ClassInfo | None:
        if class_name in class_infos:
            return class_infos[class_name]
        return next((info for info in class_infos.values() if info.name == class_name), None)

    def _value_typedef_dependency_names(
        self: HeaderGeneratorContext,
        underlying_type: str,
        class_infos: dict[str, ClassInfo],
    ) -> set[str]:
        dependencies = self._typedef_dependency_names(underlying_type, class_infos)
        known_names = set(class_infos)
        known_names.update(info.name for info in class_infos.values())
        direct = self._referenced_class_name(underlying_type, known_names)
        if direct:
            dependencies.add(direct)
        for expression in self._template_expressions(underlying_type):
            dependencies.update(self._template_specialization_names(expression, known_names))
        return dependencies

    @classmethod
    def _all_nested_members(cls, class_info: ClassInfo) -> list[MemberInfo]:
        members = list(class_info.members)
        members.extend(member for struct in class_info.nested_structs for member in struct.members)
        members.extend(member for union in class_info.unions for member in union.members)
        members.extend(
            member
            for union in class_info.unions
            for struct in union.nested_structs
            for member in struct.members
        )
        for nested_class in class_info.nested_classes:
            members.extend(cls._all_nested_members(nested_class))
        return members

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
        offset_names: dict[int, str] | None = None,
    ) -> None:
        # Recovered template specializations are rendered as one primary
        # template definition. Their element types are represented by the
        # recovered storage, so importing every concrete argument's header
        # creates avoidable include cycles such as cArray<unZoneGroup, 8>.
        if "<" in class_name:
            return
        for member in members:
            dependencies[class_name].update(
                self._member_dependency_names(member, class_name, names, offset_names)
            )

    def _member_dependency_names(
        self: HeaderGeneratorContext,
        member: MemberInfo,
        class_name: str,
        names: set[str],
        offset_names: dict[int, str] | None,
    ) -> set[str]:
        if member.is_static or "*" in member.type_name or "&" in member.type_name:
            return set()
        dependencies = {
            referenced_name
            for referenced_name in self._referenced_dependency_names(member.type_name, names)
            if referenced_name != class_name
        }
        if member.type_offset is not None and offset_names:
            referenced_name = offset_names.get(member.type_offset)
            if referenced_name and referenced_name != class_name:
                dependencies.add(referenced_name)
        return dependencies

    def _referenced_dependency_names(
        self: HeaderGeneratorContext, type_name: str, names: set[str]
    ) -> set[str]:
        dependencies: set[str] = set()
        referenced_name = self._referenced_class_name(type_name, names)
        if referenced_name:
            dependencies.add(referenced_name)
        for expression in self._template_expressions(type_name):
            dependencies.update(self._template_specialization_names(expression, names))
        return dependencies

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
        if class_info.name in {
            "void",
            "unknown_type",
            "base_type",
            "subroutine_type",
            "pointer_type",
            "ptr_to_member_type",
        }:
            return None
        if not re.fullmatch(r"[A-Za-z_]\w*", class_info.name):
            return None
        kind = class_info.kind if class_info.kind in {"class", "struct", "union"} else "class"
        return f"{kind} {class_info.name};"

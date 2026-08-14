"""Nested aggregate rendering and ordering operations for generated headers."""

from __future__ import annotations

from ...models.dwarf import ClassInfo, MemberInfo, StructInfo, UnionInfo
from .rendering.operations import HeaderRenderingHost


class HeaderNestedRenderingService:
    def _nested_type_lines(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        return [
            *self._nested_type_forward_declarations(class_info),
            *self._enum_lines(class_info, include_metadata),
            *self._nested_aggregate_definition_lines(class_info),
        ]

    def _nested_aggregate_definition_lines(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        units = self._ordered_nested_aggregates(class_info)
        if not units:
            return []
        lines = ["public:"]
        for index, (kind, aggregate) in enumerate(units):
            if kind == "class":
                assert isinstance(aggregate, ClassInfo)
                nested_lines = self._generate_single_class(aggregate, include_metadata=False)
                lines.extend(f"    {line}" if line else "" for line in nested_lines)
            elif kind == "struct":
                assert isinstance(aggregate, StructInfo)
                rendered_name = f"anonymous_struct_{index}" if not aggregate.name else None
                lines.extend(
                    self._generate_struct_definition(aggregate, class_info.name, rendered_name)
                )
            else:
                assert isinstance(aggregate, UnionInfo)
                lines.extend(
                    self._generate_union_definition(
                        aggregate, class_info.name, self._member_names(class_info)
                    )
                )
        return lines

    def _ordered_nested_aggregates(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[tuple[str, ClassInfo | StructInfo | UnionInfo]]:
        units: dict[str, tuple[str, ClassInfo | StructInfo | UnionInfo]] = {}
        for nested_class in self._ordered_nested_classes(class_info.nested_classes):
            units[self._nested_definition_key(nested_class.name)] = ("class", nested_class)
        for index, struct in enumerate(class_info.nested_structs):
            key = self._nested_definition_key(struct.name) if struct.name else f"__struct_{index}"
            units.setdefault(key, ("struct", struct))
        for index, union in enumerate(class_info.unions):
            key = self._nested_definition_key(union.name) if union.name else f"__union_{index}"
            units.setdefault(key, ("union", union))

        names = set(units)
        dependencies = {
            key: self._nested_aggregate_dependencies(kind, aggregate, key, names)
            for key, (kind, aggregate) in units.items()
        }
        preferred = list(units)
        try:
            ordered_names = self._stable_topological_order(dependencies, preferred)
        except ValueError:
            ordered_names = preferred
        return [units[name] for name in ordered_names]

    def _nested_aggregate_dependencies(
        self: HeaderRenderingHost,
        kind: str,
        aggregate: ClassInfo | StructInfo | UnionInfo,
        key: str,
        names: set[str],
    ) -> set[str]:
        members, bases = self._nested_aggregate_parts(kind, aggregate)
        dependencies = {
            self._nested_definition_key(self._normalize_type_name(type_name))
            for type_name in [*bases, *(member.type_name for member in members)]
            if "*" not in type_name and "&" not in type_name
        }
        return {
            dependency for dependency in dependencies if dependency in names and dependency != key
        }

    def _nested_aggregate_parts(
        self: HeaderRenderingHost,
        kind: str,
        aggregate: ClassInfo | StructInfo | UnionInfo,
    ) -> tuple[list[MemberInfo], list[str]]:
        if kind == "class":
            assert isinstance(aggregate, ClassInfo)
            members = self._all_nested_members(aggregate)
            bases = aggregate.base_classes
        elif kind == "struct":
            assert isinstance(aggregate, StructInfo)
            members = aggregate.members
            bases = []
        else:
            assert isinstance(aggregate, UnionInfo)
            members = list(aggregate.members)
            members.extend(
                member for struct in aggregate.nested_structs for member in struct.members
            )
            bases = []
        return members, bases

    def _ordered_nested_classes(
        self: HeaderRenderingHost, nested_classes: list[ClassInfo]
    ) -> list[ClassInfo]:
        """Order nested classes by their inheritance and by-value dependencies."""
        candidates: dict[str, ClassInfo] = {}
        for nested_class in nested_classes:
            key = self._nested_definition_key(nested_class.name)
            current = candidates.get(key)
            if current is None or self._nested_class_richness(
                nested_class
            ) > self._nested_class_richness(current):
                candidates[key] = nested_class
        names = set(candidates)
        dependencies = {
            key: self._nested_class_dependencies(info, names) for key, info in candidates.items()
        }
        preferred = list(candidates)
        try:
            ordered_names = self._stable_topological_order(dependencies, preferred)
        except ValueError:
            ordered_names = preferred
        return [candidates[name] for name in ordered_names]

    def _nested_class_dependencies(
        self: HeaderRenderingHost, class_info: ClassInfo, names: set[str]
    ) -> set[str]:
        dependencies: set[str] = set()
        for base_name in class_info.base_classes:
            dependency = self._nested_definition_key(base_name)
            if dependency in names and dependency != self._nested_definition_key(class_info.name):
                dependencies.add(dependency)
        for member in self._all_nested_members(class_info):
            if member.is_static or "*" in member.type_name or "&" in member.type_name:
                continue
            dependency = self._nested_definition_key(self._normalize_type_name(member.type_name))
            if dependency in names and dependency != self._nested_definition_key(class_info.name):
                dependencies.add(dependency)
        return dependencies

    def _nested_definition_key(self: HeaderRenderingHost, name: str) -> str:
        template_info = self._template_rendering_info(name)
        if template_info:
            return template_info[0]
        return self._unqualify_type_expression(name).split("<", 1)[0].strip()

    @staticmethod
    def _nested_class_richness(class_info: ClassInfo) -> int:
        return (
            len(class_info.members)
            + 2 * len(class_info.methods)
            + len(class_info.nested_classes)
            + len(class_info.nested_structs)
            + len(class_info.enums)
            + len(class_info.unions)
        )

    def _nested_type_forward_declarations(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        declarations = [
            *self._nested_enum_forward_declarations(class_info),
            *self._nested_struct_forward_declarations(class_info),
            *self._nested_class_forward_declarations(class_info),
            *self._nested_union_forward_declarations(class_info),
        ]
        declarations = list(dict.fromkeys(declarations))
        return ["public:", *declarations] if declarations else []

    def _nested_enum_forward_declarations(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        return [
            f"    enum class {self._unqualify_type_expression(enum.name)};"
            for enum in class_info.enums
            if enum.name and enum.name != "unknown_enum"
        ]

    def _nested_struct_forward_declarations(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        return [
            f"    struct {self._unqualify_type_expression(struct.name)};"
            for struct in class_info.nested_structs
            if struct.name
        ]

    def _nested_class_forward_declarations(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        declarations: list[str] = []
        for nested_class in self._ordered_nested_classes(class_info.nested_classes):
            if not nested_class.name:
                continue
            if "<" in nested_class.name:
                declaration = self._aggregate_forward_declaration(nested_class.name)
                if declaration is not None:
                    declarations.append(f"    {declaration}")
                continue
            kind = (
                nested_class.kind if nested_class.kind in {"class", "struct", "union"} else "class"
            )
            declarations.append(f"    {kind} {self._unqualify_type_expression(nested_class.name)};")
        return declarations

    def _nested_union_forward_declarations(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> list[str]:
        return [
            f"    union {self._unqualify_type_expression(union.name)};"
            for union in class_info.unions
            if union.name
        ]

    def _enum_lines(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        if not class_info.enums:
            return []
        lines = ["public:"]
        for enum in class_info.enums:
            lines.extend(self._generate_enum_definition(enum, include_metadata))
        return lines

    def _struct_lines(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        if not class_info.nested_structs:
            return []
        lines = ["public:"]
        for index, struct in enumerate(self._ordered_structs(class_info.nested_structs)):
            rendered_name = f"anonymous_struct_{index}" if not struct.name else None
            lines.extend(self._generate_struct_definition(struct, class_info.name, rendered_name))
        return lines

    def _nested_class_lines(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        if not class_info.nested_classes:
            return []
        lines = ["public:"]
        for nested_class in self._ordered_nested_classes(class_info.nested_classes):
            nested_lines = self._generate_single_class(nested_class, include_metadata=False)
            lines.extend(f"    {line}" if line else "" for line in nested_lines)
        return lines

    def _union_lines(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        if not class_info.unions:
            return []
        lines = ["public:"]
        for union in class_info.unions:
            lines.extend(
                self._generate_union_definition(
                    union, class_info.name, self._member_names(class_info)
                )
            )
        return lines

    @staticmethod
    def _member_names(class_info: ClassInfo) -> set[str]:
        return {member.name for member in class_info.members if member.name}

"""Narrow type-name resolution port used by array parsing."""

from __future__ import annotations

from typing import Protocol

from elftools.dwarf.die import DIE

from ..models.dwarf import MemberInfo, MethodInfo, StructInfo, UnionInfo


class TypeNameResolver(Protocol):
    """Minimum resolver surface required to render an array element type."""

    def resolve_type_name(self, die: DIE, type_attr_name: str = "DW_AT_type") -> str: ...


class TypeResolverPort(TypeNameResolver, Protocol):
    """Extended resolver surface required by application workflows."""

    def expand_primitive_search(self, full_hierarchy: bool = False) -> None: ...

    def collect_used_typedefs(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None = None,
        nested_structs: list[StructInfo] | None = None,
    ) -> dict[str, str]: ...

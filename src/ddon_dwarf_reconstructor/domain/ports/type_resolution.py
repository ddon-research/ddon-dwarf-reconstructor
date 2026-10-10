"""Narrow type-name resolution port used by array parsing."""

from __future__ import annotations

from typing import Protocol

from ...core.dwarf import DwarfEntry
from ..models.dwarf import MemberInfo, MethodInfo, StructInfo, TypeReference, UnionInfo


class TypeNameResolver(Protocol):
    """Minimum resolver surface required to render an array element type."""

    def resolve_type_name(self, die: DwarfEntry, type_attr_name: str = "DW_AT_type") -> str: ...

    def resolve_die_type(self, type_die: DwarfEntry) -> str: ...


class TypeReferenceResolver(Protocol):
    """Narrow semantic type resolver consumed by array projections."""

    def resolve_type_reference(self, type_die: DwarfEntry) -> TypeReference: ...


class TypeResolverPort(TypeNameResolver, TypeReferenceResolver, Protocol):
    """Extended resolver surface required by application workflows."""

    def resolve_reference(self, die: DwarfEntry) -> TypeReference: ...

    def anonymous_typedef_die(self, die: DwarfEntry) -> DwarfEntry | None: ...

    def resolve_typedef_chain(self, typedef_name: str) -> str: ...

    def expand_primitive_search(self, full_hierarchy: bool = False) -> None: ...

    def collect_used_typedefs(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None = None,
        nested_structs: list[StructInfo] | None = None,
    ) -> dict[str, str]: ...

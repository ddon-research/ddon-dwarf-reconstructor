"""Typed collaboration contract for lazy type-resolution mixins."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from ....core.dwarf import DwarfEntry, DwarfInfo
from ...models.dwarf import MemberInfo, MethodInfo, StructInfo, UnionInfo
from ...ports.dwarf_lookup import DwarfLookupPort


class TypeResolverContext(Protocol):
    """State and operations shared by the type-resolution responsibilities."""

    dwarf_info: DwarfInfo
    index: DwarfLookupPort
    _typedef_cache: dict[int, str]
    _type_name_cache: dict[int, str]
    _typedef_chains: dict[str, str]
    _types_in_progress: set[str]
    _primitive_typedefs: set[str]

    def resolve_type_name(self, die: DwarfEntry, type_attr_name: str = "DW_AT_type") -> str: ...

    def _resolve_die_type_name(self, type_die: DwarfEntry) -> str: ...

    def _resolve_qualified_type(self, type_die: DwarfEntry) -> str: ...

    def find_typedef(self, typedef_name: str) -> tuple[str, str] | None: ...

    def resolve_typedef_chain(self, typedef_name: str) -> str: ...

    def _resolve_primitive_typedef(self, typedef_name: str) -> str | None: ...

    def _get_primitive_base_type_name(self, type_die: DwarfEntry) -> str: ...

    def _extract_base_type(self, type_name: str) -> str: ...

    def _is_known_aggregate_type(self, type_name: str, type_offset: int | None) -> bool: ...

    def _candidate_type_names(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> set[str]: ...

    def _resolve_candidate_typedefs(self, type_names: set[str]) -> dict[str, str]: ...

    def _resolve_declared_typedefs(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> dict[str, str]: ...

    def _declared_typedef_references(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> Iterator[tuple[str, int]]: ...

    def _member_typedef_references(
        self, members: list[MemberInfo]
    ) -> Iterator[tuple[str, int]]: ...

    def _parameter_typedef_references(self, method: MethodInfo) -> Iterator[tuple[str, int]]: ...

    def _named_type_name(self, type_die: DwarfEntry) -> str: ...

    def _resolve_array_type(self, type_die: DwarfEntry) -> str: ...

    def _resolve_referenced_name(
        self, type_die: DwarfEntry, missing_name: str, suffix: str = ""
    ) -> str: ...

    def _resolve_member_pointer_name(self, type_die: DwarfEntry) -> str: ...

    def _resolve_subroutine_name(self, type_die: DwarfEntry) -> str: ...

    def _named_or_typedef_name(self, type_die: DwarfEntry) -> str: ...

    def _qualified_primitive_name(self, type_die: DwarfEntry) -> str: ...

    def _special_primitive_name(self, type_die: DwarfEntry) -> str: ...

    def _die_name(self, type_die: DwarfEntry) -> str | None: ...

    def _strip_type_qualifiers(self, type_name: str) -> str: ...

    def _strip_array_suffix(self, type_name: str) -> str: ...

    def _strip_indirection(self, type_name: str) -> str: ...

    def _lookup_primitive_offset(self, type_name: str) -> int | None: ...

    def _resolve_primitive_die(self, type_name: str, die: DwarfEntry) -> str | None: ...

    def _type_references(
        self,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> Iterator[tuple[str, int | None, bool]]: ...

    def _parameter_references(
        self, method: MethodInfo
    ) -> Iterator[tuple[str, int | None, bool]]: ...

    def _aggregate_references(
        self, members: list[MemberInfo]
    ) -> Iterator[tuple[str, int | None, bool]]: ...

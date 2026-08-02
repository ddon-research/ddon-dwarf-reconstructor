"""Used-typedef collection for generated declaration workflows."""

from __future__ import annotations

from collections.abc import Iterator

from ....core.observability import get_logger
from ...models.dwarf import MemberInfo, MethodInfo, StructInfo, UnionInfo
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)

_EXCLUDED_TYPES = frozenset(
    {
        "void",
        "int",
        "char",
        "float",
        "double",
        "bool",
        "unsigned",
        "signed",
        "short",
        "long",
        "unknown_type",
        "class_type",
        "structure_type",
        "union_type",
        "anonymous_struct",
        "subroutine_type",
        "unsigned char",
        "signed char",
        "unsigned short",
        "signed short",
        "unsigned int",
        "signed int",
        "unsigned long",
        "signed long",
        "long long",
        "unsigned long long",
        "signed long long",
    }
)
_INVALID_RESOLVED_TYPES = frozenset(
    {
        "unknown_type",
        "class_type",
        "structure_type",
        "union_type",
        "pointer_type",
        "subroutine_type",
        "ptr_to_member_type",
    }
)


class UsedTypedefCollectionMixin:
    def collect_used_typedefs(
        self: TypeResolverContext,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None = None,
        nested_structs: list[StructInfo] | None = None,
    ) -> dict[str, str]:
        """Collect and resolve typedef names referenced by declaration models."""
        direct = self._resolve_declared_typedefs(members, methods, unions, nested_structs)
        type_names = self._candidate_type_names(members, methods, unions, nested_structs)
        type_names.difference_update(direct)
        return {**self._resolve_candidate_typedefs(type_names), **direct}

    def _resolve_declared_typedefs(
        self: TypeResolverContext,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> dict[str, str]:
        found: dict[str, str] = {}
        for type_name, offset in self._declared_typedef_references(
            members, methods, unions, nested_structs
        ):
            alias = self._extract_base_type(type_name)
            if alias in self._primitive_typedefs or alias in _EXCLUDED_TYPES:
                continue
            die = self.index.get_die_by_offset(offset)
            if die is None or die.tag != "DW_TAG_typedef":
                continue
            resolved_type = self._resolve_primitive_die(alias, die)
            if resolved_type and resolved_type not in _INVALID_RESOLVED_TYPES:
                found[alias] = resolved_type
        return found

    def _declared_typedef_references(
        self: TypeResolverContext,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> Iterator[tuple[str, int]]:
        yield from self._member_typedef_references(members)
        for method in methods:
            if method.declared_return_type_offset is not None:
                yield method.return_type, method.declared_return_type_offset
            yield from self._parameter_typedef_references(method)
        for union in unions or []:
            yield from self._member_typedef_references(union.members)
            for struct in union.nested_structs:
                yield from self._member_typedef_references(struct.members)
        for struct in nested_structs or []:
            yield from self._member_typedef_references(struct.members)

    @staticmethod
    def _member_typedef_references(members: list[MemberInfo]) -> Iterator[tuple[str, int]]:
        for member in members:
            if member.declared_type_offset is not None and member.type_name:
                yield member.type_name, member.declared_type_offset

    @staticmethod
    def _parameter_typedef_references(method: MethodInfo) -> Iterator[tuple[str, int]]:
        for parameter in method.parameters or []:
            if parameter.declared_type_offset is not None and parameter.type_name:
                yield parameter.type_name, parameter.declared_type_offset

    def _candidate_type_names(
        self: TypeResolverContext,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> set[str]:
        names: set[str] = set()
        for type_name, type_offset, check_aggregate in self._type_references(
            members, methods, unions, nested_structs
        ):
            base_type = self._extract_base_type(type_name)
            if base_type in _EXCLUDED_TYPES:
                continue
            if check_aggregate and self._is_known_aggregate_type(base_type, type_offset):
                continue
            names.add(base_type)
        return names

    def _type_references(
        self: TypeResolverContext,
        members: list[MemberInfo],
        methods: list[MethodInfo],
        unions: list[UnionInfo] | None,
        nested_structs: list[StructInfo] | None,
    ) -> Iterator[tuple[str, int | None, bool]]:
        # Inspect the terminal DIE before probing the name as a typedef.  A
        # member can refer directly to an aggregate that is absent from the
        # dump's global-name index; probing that name would trigger an
        # unbounded targeted CU scan on a cold source-bound cache.
        yield from ((member.type_name, member.type_offset, True) for member in members)
        for method in methods:
            if method.return_type:
                yield method.return_type, method.return_type_offset, True
            yield from self._parameter_references(method)
        for union in unions or []:
            yield from self._aggregate_references(union.members)
            for struct in union.nested_structs:
                yield from self._aggregate_references(struct.members)
        for struct in nested_structs or []:
            yield from self._aggregate_references(struct.members)

    @staticmethod
    def _parameter_references(method: MethodInfo) -> Iterator[tuple[str, int | None, bool]]:
        for parameter in method.parameters or []:
            if parameter.type_name:
                yield parameter.type_name, parameter.type_offset, True

    @staticmethod
    def _aggregate_references(
        members: list[MemberInfo],
    ) -> Iterator[tuple[str, int | None, bool]]:
        for member in members:
            if member.type_name:
                yield member.type_name, member.type_offset, True

    def _resolve_candidate_typedefs(
        self: TypeResolverContext, type_names: set[str]
    ) -> dict[str, str]:
        found: dict[str, str] = {}
        for type_name in sorted(type_names):
            if any(symbol in type_name for symbol in ("*", "&", "[")):
                continue
            resolved_type = self._resolve_primitive_typedef(type_name)
            if resolved_type is None or resolved_type == type_name:
                continue
            if resolved_type in _INVALID_RESOLVED_TYPES:
                continue
            found[type_name] = resolved_type
        logger.debug("Collected %s typedefs", len(found))
        return found

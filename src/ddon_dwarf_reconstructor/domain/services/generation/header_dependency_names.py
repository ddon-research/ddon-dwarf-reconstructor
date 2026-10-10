"""Source-bound identities and names used by header dependency planning."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping

from ...models.dwarf import ClassInfo, MemberInfo, MethodInfo, TypeReference
from .header_type_planning import HeaderTypePlanningService


def _offset_name_index(class_infos: Mapping[str, ClassInfo]) -> dict[tuple[int | None, int], str]:
    """Index only unambiguous CU/DIE identities; offset zero is valid."""
    candidates: dict[tuple[int | None, int], set[str]] = {}
    for name, info in class_infos.items():
        if info.cu_offset is not None and info.die_offset is not None:
            candidates.setdefault((info.cu_offset, info.die_offset), set()).add(name)
    return {key: next(iter(names)) for key, names in candidates.items() if len(names) == 1}


def _base_offset_dependencies(
    info: ClassInfo, offset_names: Mapping[tuple[int | None, int], str]
) -> set[str]:
    """Resolve inheritance type DIEs without choosing a same-spelling class."""
    return {
        name
        for offset in info.base_class_offsets
        if (name := offset_names.get((info.cu_offset, offset))) is not None
    }


def _type_offset_key(
    cu_offset: int | None, type_offset: int | None, reference: TypeReference | None = None
) -> tuple[int | None, int] | None:
    if type_offset is None:
        return None
    if (
        reference is not None
        and reference.die_offset == type_offset
        and reference.cu_offset is not None
    ):
        cu_offset = reference.cu_offset
    if cu_offset is None:
        return None
    return cu_offset, type_offset


def _aggregate_members(info: ClassInfo) -> Iterator[MemberInfo]:
    yield from info.members
    for struct in info.nested_structs:
        yield from struct.members
    for union in info.unions:
        yield from union.members
        for struct in union.nested_structs:
            yield from struct.members


def _member_references(member: MemberInfo) -> Iterator[TypeReference]:
    if member.type_reference is not None:
        yield member.type_reference
    yield from member.template_arguments
    if member.inline_struct is not None:
        for child in member.inline_struct.members:
            yield from _member_references(child)


def _method_references(method: MethodInfo) -> Iterator[TypeReference]:
    if method.return_type_reference is not None:
        yield method.return_type_reference
    for parameter in method.parameters or ():
        if parameter.type_reference is not None:
            yield parameter.type_reference


def _class_type_references(info: ClassInfo) -> Iterator[TypeReference]:
    """Visit typed uses at this owner; nested classes are planned separately."""
    for member in _aggregate_members(info):
        yield from _member_references(member)
    for method in info.methods:
        yield from _method_references(method)
    yield from info.declared_aliases
    yield from info.source_aliases


def _lexical_owner_dependencies(
    info: ClassInfo,
    name_index: Mapping[str, str],
    offset_names: Mapping[tuple[int | None, int], str],
) -> set[str]:
    """Require the enclosing aggregate before naming its nested declarations."""
    owners: set[str] = set()
    for root in _class_type_references(info):
        for reference in root.references():
            scope = reference.scope
            if not scope.complete or (owner_name := scope.containing_aggregate) is None:
                continue
            component = next(
                part for part in reversed(scope.components) if part.kind != "namespace"
            )
            owner = (
                offset_names.get((component.cu_offset, component.die_offset))
                if component.die_offset is not None
                else None
            )
            owner = owner or _resolve_class_name(owner_name, name_index)
            if owner is not None:
                owners.add(owner)
    return owners


def _owner_dependencies_for_class(
    info: ClassInfo,
    name_index: Mapping[str, str],
    offset_names: Mapping[tuple[int | None, int], str],
) -> set[str]:
    """Include nested class uses in the enclosing header's owner requirements."""
    owners = _lexical_owner_dependencies(info, name_index, offset_names)
    for nested in info.nested_classes:
        owners.update(_owner_dependencies_for_class(nested, name_index, offset_names))
    return owners


def _nested_names(class_info: ClassInfo) -> set[str]:
    nested = tuple(HeaderTypePlanningService._iter_nested_classes(class_info))
    names = {item.name for item in nested}
    names.update(item.qualified_name for item in nested if item.qualified_name)
    return names


def _resolve_class_name(type_name: str, name_index: Mapping[str, str]) -> str | None:
    lookup_name = HeaderTypePlanningService._lookup_type_name(type_name)
    clean_name = HeaderTypePlanningService._normalize_type_name(type_name)
    if not clean_name:
        return None
    primary, normalized_primary = _type_primary_names(lookup_name, clean_name)
    qualified_primary = "::" in primary
    candidates = (
        (lookup_name, primary)
        if qualified_primary
        else _class_name_candidates(lookup_name, primary, clean_name, normalized_primary)
    )
    ambiguous = getattr(name_index, "ambiguous", {})
    for value in candidates:
        if value in ambiguous:
            return None
        if value in name_index:
            return name_index[value]
    specializations = _indexed_specializations(
        name_index, primary, primary if qualified_primary else normalized_primary
    )
    return specializations[0] if len(specializations) == 1 else None


def _type_primary_names(lookup_name: str, clean_name: str) -> tuple[str, str]:
    pattern = r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*(?:<|$)"
    lookup_match = re.match(pattern, lookup_name)
    normalized_match = re.match(pattern, clean_name)
    primary = lookup_match.group(1) if lookup_match else re.split(r"[\s\[]", lookup_name)[0]
    normalized = (
        normalized_match.group(1) if normalized_match else re.split(r"[\s\[]", clean_name)[0]
    )
    return primary, normalized


def _class_name_candidates(
    lookup_name: str, primary: str, clean_name: str, normalized_primary: str
) -> tuple[str, ...]:
    return (lookup_name, primary, clean_name, normalized_primary)


def _indexed_specializations(
    name_index: Mapping[str, str], primary: str, normalized_primary: str
) -> tuple[str, ...]:
    indexed = getattr(name_index, "specializations", None)
    if indexed is not None:
        return indexed.get(primary, ()) or indexed.get(normalized_primary, ())
    return tuple(
        sorted(
            key
            for value, key in name_index.items()
            if value.startswith(f"{primary}<") or value.startswith(f"{normalized_primary}<")
        )
    )


def _requires_complete_method_signature(type_name: str) -> bool:
    """Return whether a method signature has a complete-header contract."""
    normalized = HeaderTypePlanningService._normalize_type_name(type_name)
    primary = normalized.split("<", 1)[0].strip()
    return primary == "MtDataReader"

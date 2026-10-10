"""Source-bound publication of namespace enums referenced by class declarations."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.content_hash import sha256_text
from ...domain.models.dwarf import ClassInfo, EnumInfo, MemberInfo, TypeReference
from ...domain.services.generation.enum_declarations import enum_head
from ...domain.services.generation.special_header_renderer import SpecialHeaderRenderer

if TYPE_CHECKING:
    from ..generation.runtime import GenerationRuntime


class EnumPublicationError(ValueError):
    """A required enum cannot be published from unambiguous source evidence."""


@dataclass(frozen=True, slots=True)
class EnumPublication:
    """Rendered enum headers and their exact consumer/provenance records."""

    headers: Mapping[str, str]
    paths_by_class: Mapping[str, Mapping[str, str]]
    identities_by_header: Mapping[str, tuple[str, ...]]
    origins_by_identity: Mapping[str, tuple[str, ...]]
    qualified_names: frozenset[str]
    paths_by_namespace: Mapping[str, str]
    enums_by_namespace: Mapping[str, Mapping[str, EnumInfo]]


def plan_namespace_enums(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    origins: Mapping[str, set[str]],
) -> EnumPublication:
    """Publish reachable complete namespace enums once across requested roots."""
    by_name, consumers, enum_origins = _collect_enums(context, class_infos, origins)
    grouped, paths_by_name = _group_enums(by_name)
    enums_by_namespace: dict[str, dict[str, EnumInfo]] = {}
    paths_by_namespace: dict[str, str] = {}
    for enum in by_name.values():
        namespace = "::".join(part.name for part in enum.scope.components)
        enums_by_namespace.setdefault(namespace, {})[enum.name] = enum
        paths_by_namespace[namespace] = paths_by_name[enum.scope.qualify(enum.name)]
    headers, identities_by_header, origins_by_identity = _render_enum_groups(grouped, enum_origins)
    return EnumPublication(
        headers,
        {
            key: {name: paths_by_name[name] for name in sorted(names)}
            for key, names in consumers.items()
        },
        identities_by_header,
        origins_by_identity,
        frozenset(by_name),
        paths_by_namespace,
        enums_by_namespace,
    )


def _collect_enums(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    origins: Mapping[str, set[str]],
) -> tuple[dict[str, EnumInfo], dict[str, set[str]], dict[str, set[str]]]:
    by_name: dict[str, EnumInfo] = {}
    consumers: dict[str, set[str]] = {}
    enum_origins: dict[str, set[str]] = {}
    parsed: dict[tuple[int | None, int | None], EnumInfo | None] = {}
    for class_key, info in sorted(class_infos.items()):
        for reference in _enum_references(info):
            source = (reference.cu_offset, reference.die_offset)
            if source not in parsed:
                parsed[source] = _source_enum(context, reference)
            enum = parsed[source]
            if enum is None:
                continue  # Nested enums are owned by their enclosing class.
            qualified = enum.scope.qualify(enum.name)
            previous = by_name.get(qualified)
            if previous is not None and _enum_signature(previous) != _enum_signature(enum):
                raise EnumPublicationError(f"Conflicting namespace enum definitions: {qualified}")
            if previous is None or _source_key(enum) < _source_key(previous):
                by_name[qualified] = enum
            consumers.setdefault(class_key, set()).add(qualified)
            enum_origins.setdefault(qualified, set()).update(origins.get(class_key, ()))
    return by_name, consumers, enum_origins


def _group_enums(
    by_name: Mapping[str, EnumInfo],
) -> tuple[dict[str, list[EnumInfo]], dict[str, str]]:
    grouped: dict[str, list[EnumInfo]] = {}
    paths_by_name: dict[str, str] = {}
    for qualified, enum in sorted(by_name.items()):
        namespace = "::".join(part.name for part in enum.scope.components)
        path = _enum_header_path(namespace)
        grouped.setdefault(path, []).append(enum)
        paths_by_name[qualified] = path
    return grouped, paths_by_name


def _render_enum_groups(
    grouped: Mapping[str, list[EnumInfo]],
    enum_origins: Mapping[str, set[str]],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    headers: dict[str, str] = {}
    identities_by_header: dict[str, tuple[str, ...]] = {}
    origins_by_identity: dict[str, tuple[str, ...]] = {}
    for path, enums in sorted(grouped.items()):
        namespace = "::".join(part.name for part in enums[0].scope.components)
        headers[path] = SpecialHeaderRenderer.render_namespace_enums(namespace, enums, path)
        identities_by_header[path] = tuple(_enum_identity(enum) for enum in enums)
        for enum in enums:
            identity = _enum_identity(enum)
            origins_by_identity[identity] = tuple(
                sorted(enum_origins[enum.scope.qualify(enum.name)])
            )
    return headers, identities_by_header, origins_by_identity


def _enum_references(info: ClassInfo) -> Iterable[TypeReference]:
    for reference in _raw_type_references(info):
        yield from (
            item for item in reference.references() if item.kind == "DW_TAG_enumeration_type"
        )
    for nested in info.nested_classes:
        yield from _enum_references(nested)


def _raw_type_references(info: ClassInfo) -> Iterable[TypeReference]:
    yield from _member_references(info.members)
    yield from _method_references(info)
    yield from _alias_references(info)
    yield from _aggregate_references(info)


def _method_references(info: ClassInfo) -> Iterable[TypeReference]:
    for method in info.methods:
        if method.return_type_reference is not None:
            yield method.return_type_reference
        for parameter in method.parameters or ():
            if parameter.type_reference is not None:
                yield parameter.type_reference


def _alias_references(info: ClassInfo) -> Iterable[TypeReference]:
    for alias in (*info.declared_aliases, *info.source_aliases):
        if alias.alias_target is not None:
            yield alias.alias_target


def _aggregate_references(info: ClassInfo) -> Iterable[TypeReference]:
    for struct in info.nested_structs:
        yield from _member_references(struct.members)
    for union in info.unions:
        yield from _member_references(union.members)
        for struct in union.nested_structs:
            yield from _member_references(struct.members)


def _member_references(members: Iterable[MemberInfo]) -> Iterable[TypeReference]:
    for member in members:
        if member.type_reference is not None:
            yield member.type_reference


def _source_enum(context: GenerationRuntime, reference: TypeReference) -> EnumInfo | None:
    if reference.cu_offset is None or reference.die_offset is None:
        raise EnumPublicationError(f"Enum lacks CU/DIE identity: {reference.name}")
    found = context.class_parser._find_die_and_cu_by_offset(reference.die_offset)
    if found is None:
        raise EnumPublicationError(f"Enum DIE unavailable: {reference.name} {reference.die_offset}")
    cu, die = found
    if cu.cu_offset != reference.cu_offset or die.tag != "DW_TAG_enumeration_type":
        raise EnumPublicationError(f"Enum source mismatch: {reference.name} {reference.die_offset}")
    enum = context.class_parser.parse_enum(die)
    if enum is None or enum.name == "unknown_enum":
        raise EnumPublicationError(
            f"Enum definition incomplete: {reference.name} {reference.die_offset}"
        )
    if not enum.scope.namespace_only:
        return None
    enum_head(enum, enum.name)
    return enum


def _enum_signature(enum: EnumInfo) -> tuple[object, ...]:
    representation = enum.representation_type.name if enum.representation_type is not None else None
    return (
        enum.byte_size,
        enum.scoped,
        enum.fixed_base_evidence,
        representation,
        tuple((item.name, item.value) for item in enum.enumerators),
    )


def _source_key(enum: EnumInfo) -> tuple[int, int]:
    if enum.cu_offset is None or enum.die_offset is None:
        raise EnumPublicationError(f"Enum lacks source identity: {enum.name}")
    return enum.cu_offset, enum.die_offset


def _enum_identity(enum: EnumInfo) -> str:
    cu, die = _source_key(enum)
    return f"{enum.scope.qualify(enum.name)}|{cu}|{die}"


def _enum_header_path(namespace: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", namespace).strip("-")[:48] or "global"
    return f"shared/{stem}-enums-{sha256_text(namespace)[:8]}.h"

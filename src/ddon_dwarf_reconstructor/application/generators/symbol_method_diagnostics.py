"""Report unresolved method type visibility in a selected symbol closure."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.models.dwarf import ClassInfo, MethodInfo
from ...domain.services.generation.header_type_planning import HeaderTypePlanningService
from ...domain.services.generation.rendering.type_policy import TypeExpressionPolicy


def _name_index(class_infos: Mapping[str, ClassInfo]) -> dict[str, str]:
    index: dict[str, str] = {}
    for name, info in class_infos.items():
        for value in (name, info.name, info.qualified_name):
            if value:
                index.setdefault(value, name)
    return index


def method_signature_diagnostics(
    class_infos: Mapping[str, ClassInfo],
    *,
    name_index: Mapping[str, str] | None = None,
    typedef_names: frozenset[str] = frozenset(),
    known_enums: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Report method types that remain declaration-only or outside the union."""
    by_offset = {
        info.die_offset: info for info in class_infos.values() if info.die_offset is not None
    }
    by_name = _name_index(class_infos) if name_index is None else name_index
    known_types = (
        frozenset(
            nested.name
            for info in class_infos.values()
            for nested in (*info.enums, *info.nested_structs, *info.unions, *info.nested_classes)
            if nested.name
        )
        | known_enums
    )
    diagnostics: list[str] = []
    for owner, class_info in sorted(class_infos.items()):
        for method in class_info.methods:
            diagnostics.extend(
                _method_dependency_diagnostics(
                    owner, method, class_infos, by_offset, by_name, typedef_names, known_types
                )
            )
    return tuple(sorted(set(diagnostics)))


def _method_dependency_diagnostics(
    owner: str,
    method: MethodInfo,
    class_infos: Mapping[str, ClassInfo],
    by_offset: Mapping[int, ClassInfo],
    by_name: Mapping[str, str],
    typedef_names: frozenset[str] = frozenset(),
    known_types: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    return tuple(
        diagnostic
        for role, type_name, type_offset in _method_signature_types(method)
        if (
            diagnostic := _signature_dependency_diagnostic(
                owner,
                method.name,
                role,
                type_name,
                type_offset,
                class_infos,
                by_offset,
                by_name,
                typedef_names,
                known_types,
            )
        )
        is not None
    )


def _method_signature_types(
    method: MethodInfo,
) -> tuple[tuple[str, str | None, int | None], ...]:
    return (("return", method.return_type, method.return_type_offset),) + tuple(
        ("parameter", parameter.type_name, parameter.type_offset)
        for parameter in method.parameters or ()
    )


def _is_signature_type_known(
    normalized: str,
    typedef_names: frozenset[str],
    known_types: frozenset[str],
) -> bool:
    return (
        not normalized
        or normalized in typedef_names
        or normalized in known_types
        or is_builtin_signature_type(normalized)
    )


def _resolve_signature_reference(
    type_offset: int | None,
    normalized: str,
    by_offset: Mapping[int, ClassInfo],
    by_name: Mapping[str, str],
    class_infos: Mapping[str, ClassInfo],
) -> ClassInfo | None:
    if type_offset is not None and type_offset in by_offset:
        return by_offset[type_offset]
    name = by_name.get(normalized)
    return class_infos.get(name) if name else None


def _signature_dependency_diagnostic(
    owner: str,
    method_name: str,
    role: str,
    type_name: str | None,
    type_offset: int | None,
    class_infos: Mapping[str, ClassInfo],
    by_offset: Mapping[int, ClassInfo],
    by_name: Mapping[str, str],
    typedef_names: frozenset[str] = frozenset(),
    known_types: frozenset[str] = frozenset(),
) -> str | None:
    normalized = HeaderTypePlanningService._normalize_type_name(type_name or "")
    if type_name is not None and type_name.strip() in known_types:
        return None
    if _is_signature_type_known(normalized, typedef_names, known_types):
        return None
    ref = _resolve_signature_reference(type_offset, normalized, by_offset, by_name, class_infos)
    if ref is not None and not ref.is_declaration:
        return None
    status = "declaration-only" if ref is not None else "unresolved"
    display = type_name or "unknown_type"
    return f"{status} method-signature {role} dependency for {owner}::{method_name}: {display}"


def is_builtin_signature_type(type_name: str) -> bool:
    """Recognize built-in declaration words without guessing aliases."""
    builtin_words = {
        "auto",
        "bool",
        "char",
        "double",
        "float",
        "int",
        "long",
        "short",
        "signed",
        "size_t",
        "unsigned",
        "void",
        "wchar_t",
    }
    return (
        not type_name
        or TypeExpressionPolicy.is_builtin(type_name)
        or set(type_name.replace("::", " ").split()).issubset(builtin_words)
    )

"""Shared planning helpers for single-file hierarchy headers."""

from __future__ import annotations

from ...models.dwarf import ClassInfo
from .header_forward_declarations import HeaderForwardDeclarationService
from .header_type_planning import HeaderTypePlanningService
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy


def qualified_base_type_names(
    class_infos: dict[str, ClassInfo],
) -> dict[tuple[int, int], str]:
    """Index nested base names only when both source offsets are known."""
    candidates: dict[tuple[int, int], set[str]] = {}

    def visit(info: ClassInfo) -> None:
        if (
            info.cu_offset is not None
            and info.die_offset is not None
            and info.containing_type
            and info.qualified_name
        ):
            candidates.setdefault((info.cu_offset, info.die_offset), set()).add(info.qualified_name)
        for nested in info.nested_classes:
            visit(nested)

    for info in class_infos.values():
        visit(info)
    return {key: next(iter(names)) for key, names in candidates.items() if len(names) == 1}


def preferred_forward_declaration(
    name: str, candidates: list[str], resolved_kinds: dict[str, str]
) -> str:
    """Choose one deterministic aggregate declaration for a spelling."""
    template = preferred_template_declaration(candidates)
    if template is not None:
        return template
    policy_kind = TypeExpressionPolicy.preferred_forward_kind(name)
    preferred_kind = select_forward_declaration_kind(name, candidates, resolved_kinds, policy_kind)
    return render_preferred_forward_declaration(name, candidates, preferred_kind, policy_kind)


def preferred_template_declaration(candidates: list[str]) -> str | None:
    """Reject disagreeing signatures instead of selecting an invented maximum arity."""
    templates = {candidate for candidate in candidates if "template <" in candidate}
    if not templates:
        return None
    if len(templates) > 1:
        raise ValueError(f"conflicting template primary declarations: {sorted(templates)}")
    return next(iter(templates))


def select_forward_declaration_kind(
    name: str,
    candidates: list[str],
    resolved_kinds: dict[str, str],
    policy_kind: str | None,
) -> str:
    if policy_kind is not None:
        return policy_kind
    resolved_kind = resolved_kinds.get(name)
    if resolved_kind is not None:
        return resolved_kind
    return next(
        (
            kind
            for kind in ("enum class", "union", "struct", "class")
            if any(declaration.startswith(f"{kind} ") for declaration in candidates)
        ),
        "class",
    )


def render_preferred_forward_declaration(
    name: str,
    candidates: list[str],
    preferred_kind: str,
    policy_kind: str | None,
) -> str:
    declaration = next(
        (candidate for candidate in candidates if candidate.startswith(f"{preferred_kind} ")),
        None,
    )
    if declaration is not None:
        return declaration
    if policy_kind is not None:
        return f"{preferred_kind} {name};"
    return candidates[0]


def collect_base_forward_declarations(
    renderer: HeaderRenderingHost,
    class_infos: dict[str, ClassInfo],
    known_infos: dict[str, ClassInfo],
    typedefs: dict[str, str] | None = None,
) -> set[str]:
    declarations: set[str] = set()
    primitives = renderer._primitive_names()
    known_names = known_base_names(renderer, known_infos)
    typedef_set = set(typedefs or {})
    for class_info in class_infos.values():
        for base_name in class_info.base_classes:
            declaration = base_forward_declaration(base_name, primitives, known_names, renderer)
            if declaration is not None:
                declarations.add(declaration)
            for expression in renderer._template_expressions(base_name):
                declarations.update(
                    renderer._template_argument_forward_declarations(expression, typedef_set)
                )
    return declarations


def hierarchy_metadata(
    class_infos: dict[str, ClassInfo],
    target_class: str,
    hierarchy_order: list[str],
    include_metadata: bool,
) -> list[str]:
    """Render stable target and inheritance metadata comments."""
    if not include_metadata or target_class not in class_infos:
        return []
    main_class = class_infos[target_class]
    lines = [
        "",
        f"// Target Class: {main_class.name}",
        f"// - Size: {main_class.byte_size} bytes",
        "// - DIE Offset: "
        + (
            f"0x{main_class.die_offset:08x}" if main_class.die_offset is not None else "unavailable"
        ),
    ]
    if main_class.packing_info:
        lines.append(
            f"// - Suggested Packing: {main_class.packing_info['suggested_packing']} bytes"
        )
    if len(hierarchy_order) > 1:
        names = [
            class_infos[name].name if name in class_infos else name for name in hierarchy_order
        ]
        lines.append(f"// - Full Inheritance Chain: {' -> '.join(names)}")
    return lines


def known_base_names(renderer: HeaderRenderingHost, known_infos: dict[str, ClassInfo]) -> set[str]:
    return {
        renderer._normalize_type_name(value)
        for info in known_infos.values()
        for value in (info.name, info.qualified_name)
        if value
    }


def base_forward_declaration(
    base_name: str,
    primitives: set[str],
    known_names: set[str],
    renderer: HeaderRenderingHost,
) -> str | None:
    if not base_name:
        return None
    clean_name = renderer._normalize_type_name(base_name)
    if not clean_name or clean_name in primitives or clean_name in known_names:
        return None
    return renderer._aggregate_forward_declaration(clean_name)


def namespace_for_info(info: ClassInfo) -> str | None:
    if info.scope is None or not info.scope.namespace_only:
        return None
    namespace = "::".join(component.name for component in info.scope.components)
    return namespace or None


def qualified_specialization_arguments(
    class_infos: dict[str, ClassInfo],
) -> tuple[set[str], set[str]]:
    """Return namespace-qualified explicit-specialization arguments."""
    qualified: set[str] = set()
    short_names: set[str] = set()
    known_class_scopes = {
        info.qualified_name or info.name
        for info in class_infos.values()
        if info.containing_type is None and info.kind in {"class", "struct", "union"}
    }
    for info in class_infos.values():
        for candidate, short in _qualified_specialization_pairs(info, known_class_scopes):
            qualified.add(candidate)
            short_names.add(short)
    return qualified, short_names


def _qualified_specialization_pairs(
    info: ClassInfo, known_class_scopes: set[str]
) -> list[tuple[str, str]]:
    class_name = info.qualified_name or info.name
    if "<" not in class_name or not class_name.endswith(">"):
        return []
    opening = class_name.find("<")
    arguments = HeaderTypePlanningService._split_template_arguments(class_name[opening + 1 : -1])
    pairs: list[tuple[str, str]] = []
    for argument in arguments:
        item = _qualified_specialization_argument(argument, known_class_scopes)
        if item is not None:
            pairs.append(item)
    return pairs


def _qualified_specialization_argument(
    argument: str, known_class_scopes: set[str]
) -> tuple[str, str] | None:
    candidate = HeaderTypePlanningService._lookup_type_name(argument)
    if "::" not in candidate or "<" in candidate:
        return None
    scope, short = candidate.rsplit("::", 1)
    if scope in known_class_scopes or TypeExpressionPolicy.is_builtin(candidate):
        return None
    return candidate, short


def repair_qualified_specialization_forwards(
    declarations: set[str], class_infos: dict[str, ClassInfo]
) -> set[str]:
    """Add namespace forwards for specialization arguments without global aliases."""
    qualified, short_names = qualified_specialization_arguments(class_infos)
    if not qualified:
        return declarations
    global_identities = {
        info.name
        for info in class_infos.values()
        if info.containing_type is None and "::" not in info.name and "<" not in info.name
    }
    result = {
        declaration
        for declaration in declarations
        if not _is_shadowed_specialization_forward(declaration, short_names, global_identities)
    }
    for candidate in sorted(qualified):
        declaration = HeaderForwardDeclarationService._aggregate_forward_declaration(candidate)
        if declaration is not None:
            result.add(declaration)
    return result


def _is_shadowed_specialization_forward(
    declaration: str, short_names: set[str], global_identities: set[str]
) -> bool:
    name = HeaderTypePlanningService._forward_declaration_name(declaration)
    return name in short_names and name not in global_identities

"""Symbol-oriented extraction and flat header rendering."""

from __future__ import annotations

import posixpath
from collections.abc import Mapping
from dataclasses import asdict, replace
from pathlib import Path

from ...core.observability import get_logger, log_event
from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import SpecialHeaderRenderer, calculate_packing_info
from ...domain.services.generation.header_dependency_plan import HeaderDependencyPlan
from ...domain.services.generation.template_families import plan_template_families
from ..generation.runtime import GenerationRuntime
from .dwarf_header_generation import HeaderGenerationService
from .dwarf_multi_file import MultiFileGenerationService
from .generation_contracts import SymbolExtractionRequest, SymbolExtractionResult
from .symbol_definition_graph import (
    CanonicalDefinitionGraph,
    build_canonical_definition_graph,
)
from .symbol_enum_publication import EnumPublication, plan_namespace_enums
from .symbol_header_layout import (
    allocate_header_paths as _allocate_header_paths,
)
from .symbol_header_layout import (
    guard_suffix as _guard_suffix,
)
from .symbol_header_layout import (
    header_groups,
)
from .symbol_header_layout import (
    header_names_for_group as _header_names_for_group,
)
from .symbol_header_validation import (
    _rendered_class_name as _symbol_rendered_class_name,
)
from .symbol_header_validation import (
    complete_definition_names,
    validate_rendered_headers,
)
from .symbol_header_validation import (
    root_statuses as _root_statuses,
)
from .symbol_method_diagnostics import method_signature_diagnostics as _method_signature_diagnostics

logger = get_logger(__name__)
_SHARED_OWNER = "shared"
_complete_definition_names = complete_definition_names
_header_groups = header_groups
_rendered_class_name = _symbol_rendered_class_name
_validate_rendered_headers = validate_rendered_headers


class SymbolExtractionService:
    """Build and render one deduplicated closure for the requested symbols."""

    @staticmethod
    def generate(
        context: GenerationRuntime,
        request: SymbolExtractionRequest,
    ) -> SymbolExtractionResult:
        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)
        class_infos, hierarchy_order = _build_requested_closure(context, request)
        graph = build_canonical_definition_graph(
            context,
            request.symbols,
            class_infos,
            hierarchy_order,
        )
        _ensure_packing_info(graph.class_infos)
        graph.class_infos, families = plan_template_families(graph.class_infos, graph.origins)
        graph.diagnostics += tuple(message for family in families for message in family.diagnostics)
        enum_publication = plan_namespace_enums(context, graph.class_infos, graph.origins)
        owners = _class_owners(graph.class_infos, graph.root_keys, graph.origins)
        groups = _header_groups(graph.class_infos, owners)
        paths = _allocate_header_paths(groups, graph.class_infos)
        dependency_plan = _build_dependency_plan(context, graph, groups)
        headers, typedef_names = _render_headers(
            context,
            graph,
            groups,
            paths,
            request.include_metadata,
            dependency_plan,
            enum_publication,
        )
        headers.update(enum_publication.headers)
        paths.update({path: (_SHARED_OWNER, ()) for path in enum_publication.headers})
        _validate_rendered_headers(headers, paths, graph.class_infos, owners)
        diagnostics = _generation_diagnostics(
            context, graph, dependency_plan, typedef_names, enum_publication.qualified_names
        )
        result = _build_extraction_result(
            request, graph, headers, paths, owners, diagnostics, enum_publication
        )
        result = replace(
            result,
            configuration={
                **result.configuration,
                "template_family_policy": "evidence-reconstruction/2",
                "template_families": [asdict(family) for family in families],
            },
        )
        _log_generation_completed(result)
        return result


def _build_requested_closure(
    context: GenerationRuntime, request: SymbolExtractionRequest
) -> tuple[dict[str, ClassInfo], list[str]]:
    return context.hierarchy_builder.build_symbol_union_with_dependencies(
        request.symbols,
        max_depth=request.max_depth,
        include_method_signatures=True,
    )


def _ensure_packing_info(class_infos: Mapping[str, ClassInfo]) -> None:
    for class_info in class_infos.values():
        if class_info.packing_info is None:
            class_info.packing_info = calculate_packing_info(class_info)


def _generation_diagnostics(
    context: GenerationRuntime,
    graph: CanonicalDefinitionGraph,
    dependency_plan: HeaderDependencyPlan | None = None,
    typedef_names: frozenset[str] = frozenset(),
    enum_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    diagnostics = list(graph.diagnostics)
    diagnostics.extend(
        _method_signature_diagnostics(
            graph.class_infos,
            name_index=dependency_plan.name_index if dependency_plan is not None else None,
            typedef_names=typedef_names,
            known_enums=enum_names,
        )
    )
    diagnostics.extend(
        _cycle_diagnostics(context, graph.class_infos, graph.hierarchy_order, dependency_plan)
    )
    if dependency_plan is not None:
        diagnostics.extend(dependency_plan.ambiguous_base_requirements)
    return tuple(sorted(diagnostics))


def _build_extraction_result(
    request: SymbolExtractionRequest,
    graph: CanonicalDefinitionGraph,
    headers: Mapping[str, str],
    paths: Mapping[str, tuple[str, tuple[str, ...]]],
    owners: Mapping[str, str],
    diagnostics: tuple[str, ...],
    enum_publication: EnumPublication,
) -> SymbolExtractionResult:
    return SymbolExtractionResult(
        requested_symbols=request.symbols,
        headers=headers,
        header_owners={path: owner for path, (owner, _group) in paths.items()},
        header_classes={path: tuple(group) for path, (_owner, group) in paths.items()},
        class_owners=owners,
        class_origins={name: tuple(sorted(values)) for name, values in graph.origins.items()},
        class_identities=graph.identities,
        class_infos=graph.class_infos,
        class_aliases=graph.aliases,
        header_enums=enum_publication.identities_by_header,
        enum_origins=enum_publication.origins_by_identity,
        diagnostics=diagnostics,
        root_statuses=_root_statuses(graph, diagnostics),
        configuration=_symbol_configuration(request),
    )


def _symbol_configuration(request: SymbolExtractionRequest) -> dict[str, object]:
    return {
        "max_depth": request.max_depth,
        "include_metadata": request.include_metadata,
        "include_method_signatures": True,
        "ownership_policy": "canonical-qualified-identity-and-reachability",
        "generation_mode": "single-root" if len(request.symbols) == 1 else "multi-symbol-union",
    }


def _log_generation_completed(result: SymbolExtractionResult) -> None:
    log_event(
        logger,
        20,
        "symbol_generation_completed",
        root_count=len(result.requested_symbols),
        class_count=result.class_count,
        header_count=result.header_count,
        shared_header_count=sum(owner == _SHARED_OWNER for owner in result.header_owners.values()),
        diagnostics=len(result.diagnostics),
    )


def _cycle_diagnostics(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    hierarchy_order: list[str],
    dependency_plan: HeaderDependencyPlan | None = None,
) -> tuple[str, ...]:
    finder = getattr(context.header_renderer, "cyclic_dependency_components", None)
    if finder is None:
        return ()
    if dependency_plan is None:
        components = finder(dict(class_infos), hierarchy_order, {})
    else:
        components = finder(dict(class_infos), hierarchy_order, {}, dependency_plan=dependency_plan)
    if not isinstance(components, (tuple, list)):
        return ()
    definition_cycles = tuple(
        "unschedulable cyclic by-value dependency for symbol rendering: " + "; ".join(component)
        for component in components
    )
    if dependency_plan is None:
        return definition_cycles
    owner_cycles = tuple(
        "cyclic lexical owner prerequisite is unscheduled: "
        + "; ".join(
            f"{name} requires owner {owner}"
            for name in component
            for owner in dependency_plan.owner_dependencies.get(name, ())
            if owner in component
        )
        + "; component: "
        + ", ".join(component)
        for component in dependency_plan.unschedulable_owner_cycles
    )
    return (*definition_cycles, *owner_cycles)


def _class_owners(
    class_infos: Mapping[str, ClassInfo],
    root_keys: Mapping[str, str],
    origins: Mapping[str, set[str]],
) -> dict[str, str]:
    root_by_key = {key: symbol for symbol, key in root_keys.items()}
    owners: dict[str, str] = {}
    family_origins: dict[str, set[str]] = {}
    for name, info in class_infos.items():
        if info.template_rendering is not None:
            family_origins.setdefault(info.template_rendering.primary, set()).update(
                origins.get(name, ())
            )
    for name in class_infos:
        plan = class_infos[name].template_rendering
        if plan is not None and len(family_origins[plan.primary]) > 1:
            owners[name] = _SHARED_OWNER
            continue
        if name in root_by_key:
            owners[name] = root_by_key[name]
            continue
        reachable = tuple(sorted(origins.get(name, ())))
        owners[name] = reachable[0] if len(reachable) == 1 else _SHARED_OWNER
    return owners


def _prepare_render_groups(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    groups: Mapping[tuple[str, str, str], tuple[str, ...]],
    paths: Mapping[str, tuple[str, tuple[str, ...]]],
    path_by_group: Mapping[tuple[str, tuple[str, ...]], str],
) -> tuple[
    dict[str, set[str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, ClassInfo]],
]:
    class_paths = {name: path for path, (_owner, group) in paths.items() for name in group}
    groups_by_path: dict[str, set[str]] = {}
    header_names_by_path: dict[str, dict[str, str]] = {}
    typedefs_by_path: dict[str, dict[str, str]] = {}
    local_infos_by_path: dict[str, dict[str, ClassInfo]] = {}
    for (owner, _source, _token), group in sorted(groups.items()):
        path = path_by_group[(owner, group)]
        if _namespace_info(class_infos, group) is not None:
            continue
        cur_dir = Path(path).parent.as_posix()
        header_names_by_path[path] = _header_names_for_group(
            class_infos, group, class_paths, cur_dir
        )
        local_infos = {name: class_infos[name] for name in group}
        local_infos_by_path[path] = local_infos
        typedefs_by_path[path] = HeaderGenerationService._collect_typedefs_and_packing(
            context, local_infos
        )
        groups_by_path[path] = set(group)
    return groups_by_path, header_names_by_path, typedefs_by_path, local_infos_by_path


def _render_headers(
    context: GenerationRuntime,
    graph: CanonicalDefinitionGraph,
    groups: Mapping[tuple[str, str, str], tuple[str, ...]],
    paths: Mapping[str, tuple[str, tuple[str, ...]]],
    include_metadata: bool,
    dependency_plan: HeaderDependencyPlan | None = None,
    enum_publication: EnumPublication | None = None,
) -> tuple[dict[str, str], frozenset[str]]:
    class_infos = graph.class_infos
    path_by_group = {(o, g): p for p, (o, g) in paths.items()}
    groups_by_path, header_names_by_path, typedefs_by_path, local_infos_by_path = (
        _prepare_render_groups(context, class_infos, groups, paths, path_by_group)
    )
    dependency_headers_by_path = _plan_group_dependency_headers(
        context,
        class_infos,
        graph.hierarchy_order,
        groups_by_path,
        header_names_by_path,
        typedefs_by_path,
        dependency_plan,
    )
    if enum_publication is not None:
        for path, names in groups_by_path.items():
            for class_key in names:
                for enum_name, enum_path in enum_publication.paths_by_class.get(
                    class_key, {}
                ).items():
                    dependency_headers_by_path.setdefault(path, {})[enum_name] = posixpath.relpath(
                        enum_path, start=posixpath.dirname(path)
                    )
    rendered: dict[str, str] = {}
    for (owner, _source, _token), group in sorted(groups.items()):
        path = path_by_group[(owner, group)]
        namespace_info = _namespace_info(class_infos, group)
        if namespace_info is not None:
            rendered[path] = _render_namespace_header(
                context, namespace_info, path, enum_publication
            )
            continue
        rendered[path] = _render_file_group_header(
            context,
            graph,
            group,
            path,
            local_infos_by_path[path],
            typedefs_by_path[path],
            header_names_by_path[path],
            dependency_headers_by_path.get(path, {}),
            include_metadata,
            dependency_plan,
        )
    typedef_names = frozenset(name for mapping in typedefs_by_path.values() for name in mapping)
    return rendered, typedef_names


def _render_file_group_header(
    context: GenerationRuntime,
    graph: CanonicalDefinitionGraph,
    group: tuple[str, ...],
    path: str,
    local_infos: dict[str, ClassInfo],
    local_typedefs: dict[str, str],
    header_names: dict[str, str],
    dependency_headers: dict[str, str],
    include_metadata: bool,
    dependency_plan: HeaderDependencyPlan | None,
) -> str:
    synthetic_source = f"symbols/{Path(path).name}"
    output = MultiFileGenerationService._render_file_headers(
        context,
        local_infos,
        graph.hierarchy_order,
        {synthetic_source: list(group)},
        local_typedefs,
        include_metadata,
        header_names,
        allow_cyclic_dependencies=True,
        dependency_headers_by_file={synthetic_source: dependency_headers},
        base_type_infos=graph.class_infos,
        target_classes_by_file={synthetic_source: _target_class_for_group(graph, group)},
        guard_suffixes_by_file={synthetic_source: _guard_suffix(path)},
        dependency_plan=dependency_plan,
    )
    if not output:
        return SpecialHeaderRenderer.render_not_found(group[0])
    return next(iter(output.values()))


def _build_dependency_plan(
    context: GenerationRuntime,
    graph: CanonicalDefinitionGraph,
    groups: Mapping[tuple[str, str, str], tuple[str, ...]],
) -> HeaderDependencyPlan | None:
    """Build one plan for normal groups while keeping namespace output lightweight."""
    if not any(_namespace_info(graph.class_infos, group) is None for group in groups.values()):
        return None
    builder = getattr(context.header_renderer, "build_dependency_plan", None)
    if not callable(builder):
        return None
    candidate = builder(graph.class_infos, graph.hierarchy_order)
    return candidate if isinstance(candidate, HeaderDependencyPlan) else None


def _plan_group_dependency_headers(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
    hierarchy_order: list[str],
    groups_by_path: Mapping[str, set[str]],
    header_names_by_path: Mapping[str, Mapping[str, str]],
    typedefs_by_path: Mapping[str, Mapping[str, str]],
    dependency_plan: HeaderDependencyPlan | None,
) -> dict[str, dict[str, str]]:
    """Plan all normal-group includes once, with a compatibility fallback for test hosts."""
    planner = getattr(context.header_renderer, "external_dependency_headers_for_group_specs", None)
    if callable(planner):
        planned = planner(
            class_infos,
            groups_by_path,
            header_names_by_path,
            typedefs_by_path,
            dependency_plan=dependency_plan,
        )
        if isinstance(planned, Mapping) and all(
            isinstance(value, Mapping) for value in planned.values()
        ):
            return {str(group_id): dict(headers) for group_id, headers in planned.items()}
    return {
        group_id: context.header_renderer.external_dependency_headers(
            dict(class_infos),
            set(rendered_names),
            dict(header_names_by_path[group_id]),
            dict(typedefs_by_path[group_id]),
        )
        for group_id, rendered_names in sorted(groups_by_path.items())
    }


def _namespace_info(
    class_infos: Mapping[str, ClassInfo], group: tuple[str, ...]
) -> ClassInfo | None:
    """Return the namespace root in a namespace-only output group."""
    namespace_infos = [class_infos[name] for name in group if class_infos[name].kind == "namespace"]
    if not namespace_infos:
        return None
    if len(namespace_infos) != 1 or len(group) != 1:
        raise ValueError("Namespace roots cannot share a rendered class header")
    return namespace_infos[0]


def _render_namespace_header(
    context: GenerationRuntime,
    namespace_info: ClassInfo,
    path: str,
    enum_publication: EnumPublication | None,
) -> str:
    """Render a namespace root through the established namespace renderer."""
    result = context.class_parser.find_class(namespace_info.name)
    if result is None:
        raise ValueError(f"Namespace root disappeared during rendering: {namespace_info.name}")
    cu, die = result
    if getattr(die, "tag", None) != "DW_TAG_namespace":
        raise ValueError(f"Resolved symbol is no longer a namespace: {namespace_info.name}")
    namespace = namespace_info.name
    enum_path = (
        enum_publication.paths_by_namespace.get(namespace) if enum_publication is not None else None
    )
    include = (
        posixpath.relpath(enum_path, start=posixpath.dirname(path))
        if enum_path is not None
        else None
    )
    return SpecialHeaderRenderer.render_namespace(
        namespace,
        cu,
        die,
        context.class_parser,
        external_enum_include=include,
        external_enums=(
            enum_publication.enums_by_namespace.get(namespace, {})
            if enum_publication is not None
            else {}
        ),
    )


def _target_class_for_group(graph: CanonicalDefinitionGraph, group: tuple[str, ...]) -> str:
    roots = tuple(sorted(graph.root_keys.values()))
    return next((root for root in roots if root in group), group[0])


__all__ = ["SymbolExtractionService"]

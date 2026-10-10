"""Single-file hierarchy header generation operations."""

from __future__ import annotations

import re

from ....core.observability import get_logger, log_timing
from ...models.dwarf import ClassInfo
from .alias_rendering import (
    external_alias_lines,
    referenced_namespace_aliases,
    scoped_typedef_line,
)
from .header_dependency_plan import HeaderDependencyPlan
from .header_guards import header_guard
from .header_hierarchy_support import (
    collect_base_forward_declarations,
    hierarchy_metadata,
    namespace_for_info,
    preferred_forward_declaration,
    qualified_base_type_names,
    repair_qualified_specialization_forwards,
)
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy
from .scoped_declarations import scoped_declaration
from .template_forward_declarations import ensure_family_plans, planned_template_forwards

logger = get_logger(__name__)


def _hierarchy_preamble(
    renderer: HeaderRenderingHost,
    class_infos: dict[str, ClassInfo],
    target_class: str,
    typedefs: dict[str, str] | None,
    dependency_headers: dict[str, str] | None,
    base_type_infos: dict[str, ClassInfo] | None,
    guard_suffix: str,
) -> tuple[list[str], str, str]:
    target_info = class_infos.get(target_class)
    rendered_target = target_info.name if target_info is not None else target_class
    guard_identity = (
        target_info.qualified_name or rendered_target
        if target_info is not None
        else rendered_target
    )
    guard_name = header_guard(guard_identity, guard_suffix)
    lines = renderer._hierarchy_header_prefix(guard_name)
    lines.extend(renderer._hierarchy_dependency_include_lines(dependency_headers))
    lines.extend(
        renderer._hierarchy_typedef_block(
            typedefs,
            rendered_target,
            class_infos,
            dependency_headers,
            base_type_infos or class_infos,
        )
    )
    return lines, rendered_target, guard_name


def _typedef_forward_lines(
    renderer: HeaderRenderingHost,
    typedefs: dict[str, str] | None,
    target_class: str,
    class_infos: dict[str, ClassInfo],
    dependency_headers: dict[str, str] | None,
    base_type_infos: dict[str, ClassInfo] | None,
) -> list[str]:
    nested_alias_names = renderer._enclosing_nested_alias_names(target_class, class_infos)
    typed_alias_names = {
        alias.name
        for alias in referenced_namespace_aliases(class_infos.values(), typedefs or {}).values()
    }
    declarations = renderer._normalize_typedef_forward_declarations(
        renderer._collect_typedef_forward_declarations(typedefs or {}), class_infos
    )
    declarations = {
        declaration
        for declaration in declarations
        if renderer._forward_declaration_name(declaration)
        not in nested_alias_names | typed_alias_names
    }
    declarations = renderer._exclude_included_forward_declarations(
        declarations, dependency_headers or {}, base_type_infos or class_infos
    )
    if not declarations:
        return []
    return [
        "// Forward declarations",
        *sorted(declarations, key=renderer._forward_declaration_order),
        "",
    ]


def _is_declared_class_alias(typedef_name: str, class_infos: dict[str, ClassInfo]) -> bool:
    return any(
        a.name == typedef_name or a.name.split("::")[-1] == typedef_name
        for info in class_infos.values()
        for a in info.declared_aliases
    )


def _typedef_definition_line(
    renderer: HeaderRenderingHost,
    typedef_name: str,
    underlying_type: str,
    target_class: str,
    class_infos: dict[str, ClassInfo],
) -> str | None:
    if renderer._normalize_type_name(underlying_type) == typedef_name:
        return None
    if renderer._is_enclosing_nested_alias(
        typedef_name, underlying_type, target_class, class_infos
    ):
        return None
    if _is_declared_class_alias(typedef_name, class_infos):
        return None
    if typedef_name == "size_t":
        return "// size_t provided by the standard C++ headers"
    rendered_type = renderer._void_alias_storage_type(underlying_type)
    if "::*" in rendered_type or "(*" in rendered_type or "(" in rendered_type:
        return f"using {typedef_name} = {rendered_type};"
    return f"typedef {rendered_type} {typedef_name};"


def _typedef_definition_lines(
    renderer: HeaderRenderingHost,
    typedefs: dict[str, str],
    target_class: str,
    class_infos: dict[str, ClassInfo],
) -> list[str]:
    lines = ["// Type definitions from DWARF"]
    namespace_aliases = referenced_namespace_aliases(class_infos.values(), typedefs)
    for typedef_name, underlying_type in renderer._ordered_typedefs(typedefs):
        line = _typedef_definition_line(
            renderer, typedef_name, underlying_type, target_class, class_infos
        )
        if line is not None:
            lines.append(scoped_typedef_line(line, namespace_aliases.get(typedef_name)))
    lines.append("")
    return lines


class HierarchyHeaderGenerationService:
    @staticmethod
    def _preferred_forward_declaration(
        name: str, candidates: list[str], resolved_kinds: dict[str, str]
    ) -> str:
        """Compatibility facade for deterministic aggregate-forward selection."""
        return preferred_forward_declaration(name, candidates, resolved_kinds)

    @log_timing
    def generate_single_file_hierarchy_header(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        target_class: str,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
        resolve_forward_declarations: bool = True,
        guard_suffix: str = "_HIERARCHY_H",
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
        allow_cyclic_dependencies: bool = False,
        *,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> str:
        """Generate one complete C++ hierarchy header."""
        class_infos = ensure_family_plans(class_infos)
        self._base_type_names = self._qualified_base_type_names(base_type_infos or class_infos)
        all_infos = {**(base_type_infos or {}), **class_infos}
        self._known_render_type_names = self._render_type_names(all_infos, typedefs or {})
        lines, rendered_target, guard_name = _hierarchy_preamble(
            self,
            class_infos,
            target_class,
            typedefs,
            dependency_headers,
            base_type_infos,
            guard_suffix,
        )
        lines.extend(
            hierarchy_metadata(class_infos, target_class, hierarchy_order, include_metadata)
        )
        forward_decls = self._hierarchy_forward_declarations(
            class_infos,
            hierarchy_order,
            typedefs,
            resolve_forward_declarations,
            dependency_headers,
            base_type_infos or class_infos,
        )
        if forward_decls:
            lines.extend(
                [
                    "",
                    "// Forward declarations",
                    *sorted(forward_decls, key=self._forward_declaration_order),
                ]
            )
        lines.extend(
            self._hierarchy_definitions(
                class_infos,
                hierarchy_order,
                include_metadata,
                typedefs or {},
                allow_cyclic_dependencies,
                known_infos=all_infos,
                dependency_plan=dependency_plan,
            )
        )

        lines.extend(["", f"#endif // {guard_name}"])

        return "\n".join(lines)

    @staticmethod
    def _qualified_base_type_names(
        class_infos: dict[str, ClassInfo],
    ) -> dict[tuple[int, int], str]:
        """Map nested aggregate DIEs to names valid outside their containing type."""
        return qualified_base_type_names(class_infos)

    @classmethod
    def _render_type_names(
        cls, class_infos: dict[str, ClassInfo], typedefs: dict[str, str]
    ) -> set[str]:
        names = set(typedefs)
        for class_info in class_infos.values():
            names.update(cls._class_render_names(class_info))
        return names

    @staticmethod
    def _class_render_names(class_info: ClassInfo) -> set[str]:
        names = {name for name in (class_info.name, class_info.qualified_name) if name}
        names.update(
            item.name for item in class_info.nested_structs + class_info.unions if item.name
        )
        for nested in class_info.nested_classes:
            names.update(name for name in (nested.name, nested.qualified_name) if name)
        return names

    @staticmethod
    def _hierarchy_header_prefix(guard_name: str) -> list[str]:
        return [
            f"#ifndef {guard_name}",
            f"#define {guard_name}",
            "",
            "#include <cstdint>",
            "",
        ]

    @staticmethod
    def _hierarchy_dependency_include_lines(
        dependency_headers: dict[str, str] | None,
    ) -> list[str]:
        if not dependency_headers:
            return []
        headers = sorted(set(dependency_headers.values()))
        return ["// Dependencies", *[f'#include "{header}"' for header in headers], ""]

    def _hierarchy_typedef_block(
        self: HeaderRenderingHost,
        typedefs: dict[str, str] | None,
        target_class: str,
        class_infos: dict[str, ClassInfo],
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
    ) -> list[str]:
        lines = _typedef_forward_lines(
            self,
            typedefs,
            target_class,
            class_infos,
            dependency_headers,
            base_type_infos,
        )
        if typedefs:
            lines.extend(_typedef_definition_lines(self, typedefs, target_class, class_infos))
        lines.extend(
            [
                "// Generated from DWARF debug information using pyelftools",
                "// Generated complete inheritance hierarchy for: " + target_class,
            ]
        )
        return lines

    @classmethod
    def _enclosing_nested_alias_names(
        cls, target_class: str, class_infos: dict[str, ClassInfo]
    ) -> set[str]:
        info = next(
            (
                candidate
                for key, candidate in class_infos.items()
                if key == target_class
                or candidate.name == target_class
                or candidate.qualified_name == target_class
            ),
            None,
        )
        if info is None:
            return set()
        names: set[str] = set()

        def visit(current: ClassInfo) -> None:
            for nested in current.nested_classes:
                if nested.name:
                    names.add(nested.name)
                if nested.qualified_name:
                    names.add(nested.qualified_name)
                visit(nested)
            for item in (*current.nested_structs, *current.unions, *current.enums):
                if item.name:
                    names.add(item.name)
            for alias in current.declared_aliases:
                names.add(alias.name)
                names.add(alias.name.split("::")[-1])

        visit(info)
        return names

    @classmethod
    def _is_enclosing_nested_alias(
        cls,
        typedef_name: str,
        underlying_type: str,
        target_class: str,
        class_infos: dict[str, ClassInfo],
    ) -> bool:
        """Avoid global aliases whose type references a nested local type."""
        nested_names = cls._enclosing_nested_alias_names(target_class, class_infos)
        if not nested_names:
            return False
        if typedef_name in nested_names:
            return True
        return any(
            bool(re.search(r"\b" + re.escape(name.split("::")[-1]) + r"\b", underlying_type))
            for name in nested_names
        )

    def _normalize_typedef_forward_declarations(
        self: HeaderRenderingHost,
        declarations: set[str],
        class_infos: dict[str, ClassInfo],
    ) -> set[str]:
        """Match template-argument forwards to resolved aggregate kinds."""
        kinds = {
            name: kind
            for info in class_infos.values()
            for name, kind in self._aggregate_kind_names(info)
        }

        normalized: set[str] = set()
        for declaration in declarations:
            match = re.fullmatch(r"(class|struct|union)\s+([A-Za-z_]\w*)\s*;", declaration)
            if not match:
                normalized.add(declaration)
                continue
            kind = (
                TypeExpressionPolicy.preferred_forward_kind(match.group(2))
                or kinds.get(match.group(2))
                or self._forward_declaration_kind(match.group(2))
            )
            kind = kind or match.group(1)
            normalized.add(f"{kind} {match.group(2)};")
        return normalized

    def _aggregate_kind_names(self: HeaderRenderingHost, info: ClassInfo) -> list[tuple[str, str]]:
        names: list[tuple[str, str]] = []
        if info.kind in {"class", "struct", "union"}:
            names.append((self._unqualify_type_expression(info.name), info.kind))
        names.extend(
            (self._unqualify_type_expression(struct.name), "struct")
            for struct in info.nested_structs
            if struct.name
        )
        names.extend(
            (self._unqualify_type_expression(union.name), "union")
            for union in info.unions
            if union.name
        )
        names.extend(
            (self._unqualify_type_expression(nested.name), nested.kind)
            for nested in info.nested_classes
            if nested.kind in {"class", "struct", "union"}
        )
        return names

    def _hierarchy_forward_declarations(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None,
        resolve_forward_declarations: bool,
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
    ) -> set[str]:
        forward_decls = self._resolved_forward_declarations(
            class_infos, typedefs or {}, resolve_forward_declarations
        )
        forward_decls = self._exclude_defined_declarations(forward_decls, class_infos)
        forward_decls.update(self._base_forward_declarations(class_infos, class_infos, typedefs))
        forward_decls = self._exclude_included_forward_declarations(
            forward_decls,
            dependency_headers or {},
            base_type_infos or class_infos,
        )
        forward_decls = planned_template_forwards(
            self, forward_decls, base_type_infos or class_infos, class_infos
        )
        deduped = self._deduplicate_forward_declarations(forward_decls, class_infos)
        deduped = repair_qualified_specialization_forwards(deduped, class_infos)
        if typedefs:
            blocked_names = set(typedefs) | {
                alias.name
                for alias in referenced_namespace_aliases(class_infos.values(), typedefs).values()
            }
            deduped = {
                decl
                for decl in deduped
                if self._forward_declaration_name(decl) not in blocked_names
            }
        return deduped

    def _exclude_included_forward_declarations(
        self: HeaderRenderingHost,
        declarations: set[str],
        dependency_headers: dict[str, str],
        base_type_infos: dict[str, ClassInfo],
    ) -> set[str]:
        """Do not redeclare types whose complete header is already included."""
        included_names: set[str] = set()
        for dependency_key in dependency_headers:
            info = base_type_infos.get(dependency_key)
            values = (
                dependency_key,
                info.name if info is not None else "",
                info.qualified_name if info is not None else "",
            )
            included_names.update(self._normalize_type_name(value) for value in values if value)
        return {
            declaration
            for declaration in declarations
            if self._normalize_type_name(self._forward_declaration_name(declaration))
            not in included_names
        }

    def _deduplicate_forward_declarations(
        self: HeaderRenderingHost,
        declarations: set[str],
        class_infos: dict[str, ClassInfo],
    ) -> set[str]:
        """Keep one aggregate kind per forward-declared C++ name."""
        by_name: dict[str, list[str]] = {}
        for declaration in declarations:
            name = self._forward_declaration_name(declaration)
            if name == declaration:
                continue
            by_name.setdefault(name, []).append(declaration)

        resolved_kinds = {
            self._unqualify_type_expression(info.name): info.kind
            for info in class_infos.values()
            if info.kind in {"class", "struct", "union"}
        }
        grouped = {declaration for candidates in by_name.values() for declaration in candidates}
        result = declarations - grouped
        for name, candidates in by_name.items():
            result.add(preferred_forward_declaration(name, candidates, resolved_kinds))
        return result

    def _resolved_forward_declarations(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str],
        enabled: bool,
    ) -> set[str]:
        if not enabled:
            return set()
        declarations: set[str] = set()
        for class_info in class_infos.values():
            # Concrete observations of an inferred primary are retained in
            # the plan/manifest, but they are not declarations emitted by
            # this header.  Feeding their nested arguments back into the
            # forward planner creates invalid namespace declarations such as
            # ``namespace cControl::cMouseExecution`` when those scopes are
            # classes rather than namespaces.
            rendering = class_info.template_rendering
            if (
                rendering is not None
                and rendering.mode == "generic"
                and not rendering.representative
            ):
                continue
            declarations.update(self._collect_forward_declarations(class_info, typedefs))
        return declarations

    def _exclude_defined_declarations(
        self: HeaderRenderingHost, declarations: set[str], class_infos: dict[str, ClassInfo]
    ) -> set[str]:
        """Keep forwards for definitions that occur later in this header.

        A declaration can be valid and necessary even when the complete type is
        rendered in the same header: DWARF order is not C++ declaration order.
        For example, ``MtFloat2A`` can mention ``MtVector3`` before the latter's
        complete definition.  Removing every forward whose name appears in
        ``class_infos`` made those headers depend on an accidental include order.
        Forwards for complete definitions imported from another header are
        removed separately by ``_exclude_included_forward_declarations``.
        """
        del class_infos
        return declarations

    def _base_forward_declarations(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        known_infos: dict[str, ClassInfo],
        typedefs: dict[str, str] | None = None,
    ) -> set[str]:
        return collect_base_forward_declarations(self, class_infos, known_infos, typedefs)

    def _hierarchy_definitions(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
        typedefs: dict[str, str] | None = None,
        allow_cyclic_dependencies: bool = False,
        *,
        known_infos: dict[str, ClassInfo] | None = None,
        dependency_plan: HeaderDependencyPlan | None = None,
    ) -> list[str]:
        ordered_classes = self._order_class_definitions(
            class_infos,
            hierarchy_order,
            typedefs,
            allow_cyclic_dependencies,
            dependency_plan=dependency_plan,
        )
        ordered_classes = self._unique_definition_names(class_infos, ordered_classes)
        if not ordered_classes:
            return []
        lines = ["", "// ========== Complete Definitions =========="]
        for class_name in ordered_classes:
            info = class_infos[class_name]
            declaration = scoped_declaration(
                info.qualified_name or info.name, info.kind, info.scope
            )
            if declaration is not None:
                lines.append(declaration)
        for class_name in ordered_classes:
            info = class_infos[class_name]
            namespace = namespace_for_info(info)
            if namespace:
                lines.extend(["", f"namespace {namespace} {{"])
            lines.extend(["", *self._generate_single_class(info, include_metadata)])
            if namespace:
                lines.extend(["", f"}}  // namespace {namespace}"])
            lines.extend(external_alias_lines(info.source_aliases))
        return lines

    def _unique_definition_names(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        ordered_classes: list[str],
    ) -> list[str]:
        """Keep one definition per rendered declaration name."""
        result = []
        seen = set()
        for key in ordered_classes:
            info = class_infos[key]
            plan = info.template_rendering
            if plan is not None:
                if plan.mode == "blocked" or not plan.representative:
                    continue
                identity = (
                    plan.primary if plan.mode == "generic" else (info.qualified_name or info.name)
                )
            else:
                identity = info.qualified_name or info.name
            if identity not in seen:
                seen.add(identity)
                result.append(key)
        return result

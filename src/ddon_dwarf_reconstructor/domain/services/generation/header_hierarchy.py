"""Single-file hierarchy header generation operations."""

from __future__ import annotations

import re

from ....core.observability import get_logger, log_timing
from ....core.path_policy import sanitize_for_filesystem
from ...models.dwarf import ClassInfo
from .header_dependency_plan import HeaderDependencyPlan
from .header_type_planning import HeaderTypePlanningService
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy
from .template_forward_declarations import ensure_family_plans, planned_template_forwards

logger = get_logger(__name__)

_QUALIFIED_BASE_CACHE: dict[tuple[int, int], dict[int, str]] = {}


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
    guard_name = f"{sanitize_for_filesystem(rendered_target).upper()}{guard_suffix}"
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


class HierarchyHeaderGenerationService:
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
        """Generate a C++ header with the complete inheritance hierarchy in one file.

        This method generates all classes in a single file with forward declarations
        for dependencies when the single-file rendering mode is selected.

        Args:
            class_infos: Dictionary of class name -> ClassInfo
            hierarchy_order: List of class names in base-to-derived order
            target_class: Primary target class name
            typedefs: Dictionary of typedef name -> underlying type
            include_metadata: Whether to include DWARF metadata comments
            resolve_forward_declarations: Query referenced DIEs when collecting
                declarations. Deterministic evidence export disables this so
                rendering cannot mutate lazy-resolution state after closure
                construction.
        Returns:
            Complete C++ header file as string
        """
        class_infos = ensure_family_plans(class_infos)
        self._base_type_names = self._qualified_base_type_names(base_type_infos or class_infos)
        self._known_render_type_names = self._render_type_names(class_infos, typedefs or {})
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
            self._hierarchy_metadata(class_infos, target_class, hierarchy_order, include_metadata)
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
            lines.extend(["", "// Forward declarations", *sorted(forward_decls)])
        lines.extend(
            self._hierarchy_definitions(
                class_infos,
                hierarchy_order,
                include_metadata,
                typedefs or {},
                allow_cyclic_dependencies,
                dependency_plan=dependency_plan,
            )
        )

        lines.extend(["", f"#endif // {guard_name}"])

        return "\n".join(lines)

    @staticmethod
    def _qualified_base_type_names(class_infos: dict[str, ClassInfo]) -> dict[int, str]:
        """Map nested aggregate DIEs to names valid outside their containing type."""
        key = (id(class_infos), len(class_infos))
        if key in _QUALIFIED_BASE_CACHE:
            return dict(_QUALIFIED_BASE_CACHE[key])
        result: dict[int, str] = {}

        def visit(info: ClassInfo) -> None:
            if info.die_offset is not None and info.containing_type and info.qualified_name:
                result[info.die_offset] = info.qualified_name
            for nested in info.nested_classes:
                visit(nested)

        for info in class_infos.values():
            visit(info)
        if len(_QUALIFIED_BASE_CACHE) > 16:
            _QUALIFIED_BASE_CACHE.clear()
        _QUALIFIED_BASE_CACHE[key] = result
        return dict(result)

    @classmethod
    def _render_type_names(
        cls, class_infos: dict[str, ClassInfo], typedefs: dict[str, str]
    ) -> set[str]:
        names = set(typedefs)
        for class_info in class_infos.values():
            names.add(class_info.name)
            if class_info.qualified_name:
                names.add(class_info.qualified_name)
            names.update(struct.name for struct in class_info.nested_structs if struct.name)
            names.update(union.name for union in class_info.unions if union.name)
            names.update(nested.name for nested in class_info.nested_classes if nested.name)
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
        lines: list[str] = []
        typedef_forward_decls = self._normalize_typedef_forward_declarations(
            self._collect_typedef_forward_declarations(typedefs or {}), class_infos
        )
        typedef_forward_decls = self._exclude_included_forward_declarations(
            typedef_forward_decls,
            dependency_headers or {},
            base_type_infos or class_infos,
        )
        if typedef_forward_decls:
            lines.extend(["// Forward declarations", *sorted(typedef_forward_decls), ""])
        if typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in self._ordered_typedefs(typedefs):
                if self._normalize_type_name(underlying_type) == typedef_name:
                    continue
                if typedef_name == "size_t":
                    lines.append("// size_t provided by the standard C++ headers")
                else:
                    rendered_type = self._void_alias_storage_type(underlying_type)
                    lines.append(f"typedef {rendered_type} {typedef_name};")
            lines.append("")
        lines.extend(
            [
                "// Generated from DWARF debug information using pyelftools",
                "// Generated complete inheritance hierarchy for: " + target_class,
            ]
        )
        return lines

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

    @staticmethod
    def _hierarchy_metadata(
        class_infos: dict[str, ClassInfo],
        target_class: str,
        hierarchy_order: list[str],
        include_metadata: bool,
    ) -> list[str]:
        if not include_metadata or target_class not in class_infos:
            return []
        main_class = class_infos[target_class]
        target_name = main_class.name
        lines = [
            "",
            f"// Target Class: {target_name}",
            f"// - Size: {main_class.byte_size} bytes",
            "// - DIE Offset: "
            + (
                f"0x{main_class.die_offset:08x}"
                if main_class.die_offset is not None
                else "unavailable"
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
        if typedefs:
            deduped = {
                decl for decl in deduped if self._forward_declaration_name(decl) not in typedefs
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
            result.add(self._preferred_forward_declaration(name, candidates, resolved_kinds))
        return result

    @staticmethod
    def _preferred_forward_declaration(
        name: str, candidates: list[str], resolved_kinds: dict[str, str]
    ) -> str:
        template_declaration = HierarchyHeaderGenerationService._preferred_template_declaration(
            candidates
        )
        if template_declaration is not None:
            return template_declaration
        policy_kind = TypeExpressionPolicy.preferred_forward_kind(name)
        preferred_kind = HierarchyHeaderGenerationService._select_forward_declaration_kind(
            name, candidates, resolved_kinds, policy_kind
        )
        return HierarchyHeaderGenerationService._render_preferred_forward_declaration(
            name, candidates, preferred_kind, policy_kind
        )

    @staticmethod
    def _preferred_template_declaration(candidates: list[str]) -> str | None:
        """Choose one stable declaration when specializations expose arities."""
        templates = [candidate for candidate in candidates if candidate.startswith("template <")]
        if not templates:
            return None
        return max(
            templates,
            key=lambda declaration: (
                len(
                    HeaderTypePlanningService._split_template_arguments(
                        declaration[len("template <") : declaration.index("> class")]
                    )
                ),
                declaration,
            ),
        )

    @staticmethod
    def _select_forward_declaration_kind(
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

    @staticmethod
    def _render_preferred_forward_declaration(
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
        return _collect_base_forward_declarations(self, class_infos, known_infos, typedefs)

    def _hierarchy_definitions(
        self: HeaderRenderingHost,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
        typedefs: dict[str, str] | None = None,
        allow_cyclic_dependencies: bool = False,
        *,
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
            lines.extend(
                ["", *self._generate_single_class(class_infos[class_name], include_metadata)]
            )
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
                    self._unqualify_type_expression(plan.primary)
                    if plan.mode == "generic"
                    else self._unqualify_type_expression(info.name)
                )
            else:
                identity = info.qualified_name or info.name
            if identity not in seen:
                seen.add(identity)
                result.append(key)
        return result


def _collect_base_forward_declarations(
    renderer: HeaderRenderingHost,
    class_infos: dict[str, ClassInfo],
    known_infos: dict[str, ClassInfo],
    typedefs: dict[str, str] | None = None,
) -> set[str]:
    declarations: set[str] = set()
    primitives = renderer._primitive_names()
    known_names = _known_base_names(renderer, known_infos)
    typedef_set = set(typedefs or {})
    for class_info in class_infos.values():
        for base_name in class_info.base_classes:
            declaration = _base_forward_declaration(renderer, base_name, primitives, known_names)
            if declaration is not None:
                declarations.add(declaration)
            for expression in renderer._template_expressions(base_name):
                declarations.update(
                    renderer._template_argument_forward_declarations(expression, typedef_set)
                )
    return declarations


def _known_base_names(renderer: HeaderRenderingHost, known_infos: dict[str, ClassInfo]) -> set[str]:
    return {
        renderer._normalize_type_name(value)
        for info in known_infos.values()
        for value in (info.name, info.qualified_name)
        if value
    }


def _base_forward_declaration(
    renderer: HeaderRenderingHost,
    base_name: str,
    primitives: set[str],
    known_names: set[str],
) -> str | None:
    if not base_name:
        return None
    clean_name = renderer._normalize_type_name(base_name)
    if not clean_name or clean_name in primitives or clean_name in known_names:
        return None
    return renderer._aggregate_forward_declaration(clean_name)

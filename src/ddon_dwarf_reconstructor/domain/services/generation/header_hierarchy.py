"""Single-file hierarchy header generation operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....core.observability import get_logger, log_timing
from ....core.path_policy import sanitize_for_filesystem
from ...models.dwarf import ClassInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HierarchyHeaderGenerationMixin:
    @log_timing
    def generate_single_file_hierarchy_header(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        target_class: str,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
        resolve_forward_declarations: bool = True,
        guard_suffix: str = "_HIERARCHY_H",
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
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
        self._base_type_names = self._qualified_base_type_names(base_type_infos or class_infos)
        self._known_render_type_names = self._render_type_names(class_infos, typedefs or {})
        sanitized_target = sanitize_for_filesystem(target_class).upper()
        guard_name = f"{sanitized_target}{guard_suffix}"
        lines = self._hierarchy_header_prefix(guard_name)
        lines.extend(self._hierarchy_dependency_include_lines(dependency_headers))
        lines.extend(self._hierarchy_typedef_block(typedefs, target_class, class_infos))
        lines.extend(
            self._hierarchy_metadata(class_infos, target_class, hierarchy_order, include_metadata)
        )
        forward_decls = self._hierarchy_forward_declarations(
            class_infos, hierarchy_order, typedefs, resolve_forward_declarations
        )
        if forward_decls:
            lines.extend(["", "// Forward declarations", *sorted(forward_decls)])
        lines.extend(
            self._hierarchy_definitions(
                class_infos, hierarchy_order, include_metadata, typedefs or {}
            )
        )

        lines.extend(["", f"#endif // {guard_name}"])

        return "\n".join(lines)

    @classmethod
    def _qualified_base_type_names(cls, class_infos: dict[str, ClassInfo]) -> dict[int, str]:
        """Map nested aggregate DIEs to names valid outside their containing type."""
        result: dict[int, str] = {}

        def visit(class_info: ClassInfo) -> None:
            if (
                class_info.die_offset is not None
                and class_info.containing_type is not None
                and class_info.qualified_name
            ):
                result[class_info.die_offset] = class_info.qualified_name
            for nested_class in class_info.nested_classes:
                visit(nested_class)

        for class_info in class_infos.values():
            visit(class_info)
        return result

    @classmethod
    def _render_type_names(
        cls, class_infos: dict[str, ClassInfo], typedefs: dict[str, str]
    ) -> set[str]:
        names = set(class_infos) | set(typedefs)
        for class_info in class_infos.values():
            names.add(class_info.name)
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
        self: HeaderGeneratorContext,
        typedefs: dict[str, str] | None,
        target_class: str,
        class_infos: dict[str, ClassInfo],
    ) -> list[str]:
        lines: list[str] = []
        typedef_forward_decls = self._normalize_typedef_forward_declarations(
            self._collect_typedef_forward_declarations(typedefs or {}), class_infos
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
        self: HeaderGeneratorContext,
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
            kind = kinds.get(match.group(2)) or self._forward_declaration_kind(match.group(2))
            kind = kind or match.group(1)
            normalized.add(f"{kind} {match.group(2)};")
        return normalized

    def _aggregate_kind_names(
        self: HeaderGeneratorContext, info: ClassInfo
    ) -> list[tuple[str, str]]:
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
        lines = [
            "",
            f"// Target Class: {target_class}",
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
            lines.append(f"// - Full Inheritance Chain: {' -> '.join(hierarchy_order)}")
        return lines

    def _hierarchy_forward_declarations(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None,
        resolve_forward_declarations: bool,
    ) -> set[str]:
        forward_decls = self._resolved_forward_declarations(
            class_infos, typedefs or {}, resolve_forward_declarations
        )
        forward_decls = self._exclude_defined_declarations(forward_decls, class_infos)
        forward_decls.update(self._base_forward_declarations(class_infos, class_infos))
        forward_decls.update(
            self._collect_resolved_forward_declarations(class_infos, hierarchy_order)
        )
        return self._deduplicate_forward_declarations(forward_decls, class_infos)

    def _deduplicate_forward_declarations(
        self: HeaderGeneratorContext,
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
        preferred_kind = resolved_kinds.get(name) or next(
            (
                kind
                for kind in ("union", "struct", "class")
                if any(declaration.startswith(f"{kind} ") for declaration in candidates)
            ),
            "class",
        )
        return next(
            (
                declaration
                for declaration in candidates
                if declaration.startswith(f"{preferred_kind} ")
            ),
            candidates[0],
        )

    def _resolved_forward_declarations(
        self: HeaderGeneratorContext,
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
        self: HeaderGeneratorContext, declarations: set[str], class_infos: dict[str, ClassInfo]
    ) -> set[str]:
        return {
            declaration
            for declaration in declarations
            if self._forward_declaration_name(declaration) not in class_infos
        }

    def _base_forward_declarations(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        known_infos: dict[str, ClassInfo],
    ) -> set[str]:
        declarations: set[str] = set()
        primitives = self._primitive_names()
        for class_info in class_infos.values():
            for base_name in class_info.base_classes:
                if not base_name or base_name in known_infos:
                    continue
                clean_name = self._normalize_type_name(base_name)
                if not clean_name or clean_name in primitives:
                    continue
                declaration = self._aggregate_forward_declaration(clean_name)
                if declaration is not None:
                    declarations.add(declaration)
        return declarations

    def _hierarchy_definitions(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
        typedefs: dict[str, str] | None = None,
    ) -> list[str]:
        ordered_classes = self._order_class_definitions(class_infos, hierarchy_order, typedefs)
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
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        ordered_classes: list[str],
    ) -> list[str]:
        """Keep one richest definition for each flattened C++ class name."""
        groups: dict[str, list[str]] = {}
        for class_name in ordered_classes:
            template_info = self._template_rendering_info(class_name)
            declaration_name = template_info[0] if template_info else class_name
            groups.setdefault(declaration_name, []).append(class_name)

        selected: dict[str, str] = {}
        for declaration_name, candidates in groups.items():
            selected[declaration_name] = max(
                candidates,
                key=lambda candidate: (
                    len(class_infos[candidate].members)
                    + 2 * len(class_infos[candidate].methods)
                    + len(class_infos[candidate].nested_classes)
                    + len(class_infos[candidate].nested_structs)
                    + len(class_infos[candidate].enums)
                    + len(class_infos[candidate].unions),
                    -candidates.index(candidate),
                ),
            )

        result: list[str] = []
        seen: set[str] = set()
        for class_name in ordered_classes:
            template_info = self._template_rendering_info(class_name)
            declaration_name = template_info[0] if template_info else class_name
            if declaration_name in seen:
                continue
            seen.add(declaration_name)
            result.append(selected[declaration_name])
        return result

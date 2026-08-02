"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

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
    ) -> str:
        """Generate C++ header with complete inheritance hierarchy (single file, legacy mode).

        This method generates all classes in a single file with forward declarations
        for dependencies. Used for backward compatibility when --full-hierarchy --single-file
        is specified.

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
        sanitized_target = sanitize_for_filesystem(target_class).upper()
        guard_name = f"{sanitized_target}{guard_suffix}"
        lines = self._hierarchy_header_prefix(guard_name)
        lines.extend(self._hierarchy_typedef_block(typedefs, target_class))
        lines.extend(
            self._hierarchy_metadata(class_infos, target_class, hierarchy_order, include_metadata)
        )
        forward_decls = self._hierarchy_forward_declarations(
            class_infos, hierarchy_order, target_class, typedefs, resolve_forward_declarations
        )
        if forward_decls:
            lines.extend(["", "// Forward declarations", *sorted(forward_decls)])
        lines.extend(self._hierarchy_definitions(class_infos, hierarchy_order, include_metadata))

        lines.extend(["", f"#endif // {guard_name}"])

        return "\n".join(lines)

    @staticmethod
    def _hierarchy_header_prefix(guard_name: str) -> list[str]:
        return [
            f"#ifndef {guard_name}",
            f"#define {guard_name}",
            "",
            "#include <cstdint>",
            "",
        ]

    def _hierarchy_typedef_block(
        self: HeaderGeneratorContext, typedefs: dict[str, str] | None, target_class: str
    ) -> list[str]:
        lines: list[str] = []
        typedef_forward_decls = self._collect_typedef_forward_declarations(typedefs or {})
        if typedef_forward_decls:
            lines.extend(["// Forward declarations", *sorted(typedef_forward_decls), ""])
        if typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in sorted(typedefs.items()):
                if typedef_name == "size_t":
                    lines.append("// size_t provided by the standard C++ headers")
                else:
                    lines.append(f"typedef {underlying_type} {typedef_name};")
            lines.append("")
        lines.extend(
            [
                "// Generated from DWARF debug information using pyelftools",
                "// Generated complete inheritance hierarchy for: " + target_class,
            ]
        )
        return lines

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
            f"// - DIE Offset: 0x{main_class.die_offset:08x}",
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
        target_class: str,
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
        return forward_decls

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

    @staticmethod
    def _base_forward_declarations(
        class_infos: dict[str, ClassInfo], known_infos: dict[str, ClassInfo]
    ) -> set[str]:
        return {
            f"class {base_name};"
            for class_info in class_infos.values()
            for base_name in class_info.base_classes
            if base_name and base_name != "unknown_type" and base_name not in known_infos
        }

    def _hierarchy_definitions(
        self: HeaderGeneratorContext,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
    ) -> list[str]:
        ordered_classes = self._order_class_definitions(class_infos, hierarchy_order)
        if not ordered_classes:
            return []
        lines = ["", "// ========== Complete Definitions =========="]
        for class_name in ordered_classes:
            lines.extend(
                ["", *self._generate_single_class(class_infos[class_name], include_metadata)]
            )
        return lines

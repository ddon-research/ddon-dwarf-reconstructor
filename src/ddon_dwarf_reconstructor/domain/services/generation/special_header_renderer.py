"""Render deterministic headers for namespaces and unresolved symbols."""

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger
from ....core.path_policy import sanitize_for_filesystem

logger = get_logger(__name__)


class SpecialHeaderRenderer:
    """Render headers that do not require full class-layout generation."""

    @staticmethod
    def render_not_found(class_name: str) -> str:
        """Render a placeholder header for an unresolved symbol."""
        guard = class_name.upper()
        return f"""#ifndef {guard}_H
#define {guard}_H

// Class '{class_name}' not found in DWARF information
// Generated from DWARF debug information using pyelftools

#endif // {guard}_H
"""

    @staticmethod
    def render_namespace(
        namespace_name: str, cu: DwarfCompilationUnit, namespace_die: DwarfEntry
    ) -> str:
        """Render a namespace header with sorted forward declarations."""
        child_items = SpecialHeaderRenderer._namespace_children(namespace_die)
        sanitized_name = sanitize_for_filesystem(namespace_name).upper()
        lines = SpecialHeaderRenderer._namespace_prefix(
            namespace_name, sanitized_name, cu, namespace_die, child_items
        )
        lines.extend(SpecialHeaderRenderer._namespace_declarations(namespace_name, child_items))
        lines.extend(
            [
                "",
                f"}}  // namespace {namespace_name}",
                "",
                f"#endif // {sanitized_name}_NAMESPACE_H",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _namespace_children(namespace_die: DwarfEntry) -> list[tuple[str, str]]:
        child_items: list[tuple[str, str]] = []
        try:
            for child in namespace_die.iter_children():
                if child.tag not in ("DW_TAG_class_type", "DW_TAG_structure_type"):
                    continue
                name_attr = child.attributes.get("DW_AT_name")
                if name_attr is None:
                    continue
                class_name = (
                    name_attr.value.decode("utf-8")
                    if isinstance(name_attr.value, bytes)
                    else str(name_attr.value)
                )
                item_type = "class" if child.tag == "DW_TAG_class_type" else "struct"
                child_items.append((item_type, class_name))
        except (AttributeError, RuntimeError, TypeError) as error:
            logger.warning(f"Error iterating namespace children: {error}")
        return sorted(child_items, key=lambda item: item[1])

    @staticmethod
    def _namespace_prefix(
        namespace_name: str,
        sanitized_name: str,
        cu: DwarfCompilationUnit,
        namespace_die: DwarfEntry,
        child_items: list[tuple[str, str]],
    ) -> list[str]:
        lines = [
            f"#ifndef {sanitized_name}_NAMESPACE_H",
            f"#define {sanitized_name}_NAMESPACE_H",
            "",
            "#include <cstdint>",
            "",
            "// Generated from DWARF debug information using pyelftools",
            f"// Target namespace: {namespace_name}",
            "",
            "// DWARF Debug Information:",
            f"// - DIE Offset: 0x{namespace_die.offset:08x}",
            f"// - Source CU: 0x{cu.cu_offset:08x}",
        ]

        decl_file = namespace_die.attributes.get("DW_AT_decl_file")
        decl_line = namespace_die.attributes.get("DW_AT_decl_line")
        if decl_file and decl_line:
            lines.append(f"// - Declaration: {decl_file.value}")
            lines.append(f"//   Line: {decl_line.value}")

        lines.extend(
            [
                "",
                f"// Namespace: {namespace_name}",
                f"// Contains {len(child_items)} type(s)",
                "",
                f"namespace {namespace_name} {{",
                "",
            ]
        )

        return lines

    @staticmethod
    def _namespace_declarations(
        namespace_name: str, child_items: list[tuple[str, str]]
    ) -> list[str]:
        if not child_items:
            return ["// No classes found in this namespace"]
        return [
            "// Forward declarations",
            *(f"{item_type} {class_name};" for item_type, class_name in child_items),
            "",
            "// To generate full headers for these classes, use:",
            *(f"//   --generate {namespace_name}::{class_name}" for _, class_name in child_items),
        ]

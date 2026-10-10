"""Render deterministic headers for namespaces and unresolved symbols."""

from collections.abc import Mapping, Sequence

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, decode_dwarf_string
from ...models.dwarf import ClassInfo, EnumInfo
from ...ports.class_parser import ClassParserPort
from .enum_declarations import enum_definition_lines
from .header_guards import header_guard
from .template_families import primary_declarations


class SpecialHeaderRenderer:
    """Render headers that do not require full class-layout generation."""

    @staticmethod
    def render_not_found(class_name: str) -> str:
        """Render a placeholder header for an unresolved symbol."""
        guard = header_guard(class_name)
        return f"""#ifndef {guard}
#define {guard}

// Class '{class_name}' not found in DWARF information
// Generated from DWARF debug information using pyelftools

#endif // {guard}
"""

    @staticmethod
    def render_namespace_enums(namespace: str, enums: Sequence[EnumInfo], path: str) -> str:
        """Render selected complete enum definitions under their proven namespace."""
        if not enums:
            raise ValueError("Namespace enum header has no definitions")
        guard = header_guard(path, "_ENUMS_H")
        lines = [f"#ifndef {guard}", f"#define {guard}", "", "#include <cstdint>", ""]
        if namespace:
            lines.extend([f"namespace {namespace} {{", ""])
        for enum in sorted(
            enums, key=lambda item: (item.name, item.cu_offset or 0, item.die_offset or 0)
        ):
            lines.extend(enum_definition_lines(enum, enum.name))
            lines.append("")
        if namespace:
            lines.extend([f"}}  // namespace {namespace}", ""])
        lines.extend([f"#endif // {guard}", ""])
        return "\n".join(lines)

    @staticmethod
    def render_namespace(
        namespace_name: str,
        cu: DwarfCompilationUnit,
        namespace_die: DwarfEntry,
        class_parser: ClassParserPort | None = None,
        *,
        external_enum_include: str | None = None,
        external_enums: Mapping[str, EnumInfo] | None = None,
    ) -> str:
        """Render a namespace header with sorted forward declarations."""
        child_items, template_infos, enums = SpecialHeaderRenderer._namespace_children(
            namespace_die, cu, class_parser
        )
        guard = header_guard(namespace_name, "_NAMESPACE_H")
        lines = SpecialHeaderRenderer._namespace_prefix(
            namespace_name, guard, cu, namespace_die, child_items, enums
        )
        if external_enums and external_enum_include is None:
            raise ValueError("External enum definitions require a published include")
        if external_enum_include is not None:
            lines.extend([f'#include "{external_enum_include}"', ""])
        template_forwards, namespace_declarations = SpecialHeaderRenderer._namespace_declarations(
            namespace_name, child_items, template_infos
        )
        lines.extend(template_forwards)
        lines.extend([f"namespace {namespace_name} {{", ""])
        lines.extend(namespace_declarations)
        if enums:
            lines.extend(["", "// Complete enum definitions"])
            for enum in enums:
                replacement = (external_enums or {}).get(enum.name)
                if replacement is not None and (
                    _enum_definition_signature(enum) != _enum_definition_signature(replacement)
                ):
                    raise ValueError(f"Conflicting published namespace enum: {enum.name}")
                if replacement is not None:
                    continue
                lines.extend(enum_definition_lines(enum, enum.name))
                lines.append("")
        lines.extend(
            [
                "",
                f"}}  // namespace {namespace_name}",
                "",
                f"#endif // {guard}",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _namespace_children(
        namespace_die: DwarfEntry,
        cu: DwarfCompilationUnit,
        class_parser: ClassParserPort | None,
    ) -> tuple[list[tuple[str, str]], dict[str, ClassInfo], tuple[EnumInfo, ...]]:
        child_items: list[tuple[str, str]] = []
        template_infos: dict[str, ClassInfo] = {}
        enums: dict[str, EnumInfo] = {}
        for child in namespace_die.iter_children():
            if child.tag == "DW_TAG_enumeration_type":
                SpecialHeaderRenderer._collect_namespace_enum(child, class_parser, enums)
                continue
            if child.tag not in ("DW_TAG_class_type", "DW_TAG_structure_type"):
                continue
            name_attr = child.attributes.get("DW_AT_name")
            if name_attr is None:
                continue
            class_name = decode_dwarf_string(name_attr.value)
            item_type = "class" if child.tag == "DW_TAG_class_type" else "struct"
            child_items.append((item_type, class_name))
            if class_parser is not None:
                info = class_parser.parse_template_declaration_info(cu, child)
                if info.template_parameters or "<" in class_name:
                    template_infos[str(child.offset)] = info
        return (
            sorted(child_items, key=lambda item: item[1]),
            template_infos,
            tuple(sorted(enums.values(), key=lambda enum: (enum.die_offset or 0, enum.name))),
        )

    @staticmethod
    def _collect_namespace_enum(
        child: DwarfEntry,
        class_parser: ClassParserPort | None,
        enums: dict[str, EnumInfo],
    ) -> None:
        declaration = child.attributes.get("DW_AT_declaration")
        if declaration is not None and bool(declaration.value):
            return
        if class_parser is None:
            raise ValueError(f"Enum parser unavailable for namespace DIE {child.offset}")
        info = class_parser.parse_enum(child)
        if info is None or info.name == "unknown_enum":
            raise ValueError(f"Incomplete namespace enum at DIE {child.offset}")
        previous = enums.get(info.name)
        if previous is not None and _enum_definition_signature(
            previous
        ) != _enum_definition_signature(info):
            raise ValueError(f"Conflicting namespace enum definitions for {info.name}")
        enums.setdefault(info.name, info)

    @staticmethod
    def _namespace_prefix(
        namespace_name: str,
        guard: str,
        cu: DwarfCompilationUnit,
        namespace_die: DwarfEntry,
        child_items: list[tuple[str, str]],
        enums: tuple[EnumInfo, ...],
    ) -> list[str]:
        lines = [
            f"#ifndef {guard}",
            f"#define {guard}",
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
                f"// Contains {len(child_items) + len(enums)} type(s)",
                "",
            ]
        )

        return lines

    @staticmethod
    def _namespace_declarations(
        namespace_name: str,
        child_items: list[tuple[str, str]],
        template_infos: dict[str, ClassInfo],
    ) -> tuple[list[str], list[str]]:
        if not child_items:
            return [], ["// No classes found in this namespace"]

        template_names = _template_names(child_items, template_infos)
        template_items = [(kind, name) for kind, name in child_items if name in template_names]
        ordinary_items = [(kind, name) for kind, name in child_items if name not in template_names]
        template_lines = SpecialHeaderRenderer._template_namespace_forwards(
            template_items, template_infos
        )
        namespace_lines = ["// Forward declarations"]
        namespace_lines.extend(
            f"{item_type} {class_name};" for item_type, class_name in ordinary_items
        )
        namespace_lines.extend(
            [
                "",
                "// To generate full headers for these classes, use:",
                *(
                    f"//   --generate {namespace_name}::{class_name}"
                    for _, class_name in child_items
                ),
            ]
        )
        return template_lines, namespace_lines

    @staticmethod
    def _template_namespace_forwards(
        items: list[tuple[str, str]], infos: dict[str, ClassInfo]
    ) -> list[str]:
        lines, diagnostics = primary_declarations(infos)
        observed = {info.name for info in infos.values()}
        lines.update(
            f"// Unresolved template signature: {name}" for _, name in items if name not in observed
        )
        lines.update(f"// Unresolved template: {diagnostic}" for diagnostic in diagnostics)
        return ["// Evidenced template declarations", *sorted(lines), ""] if lines else []


def _template_names(items: list[tuple[str, str]], infos: dict[str, ClassInfo]) -> set[str]:
    names = {info.name for info in infos.values()}
    names.update(name for _, name in items if "<" in name)
    return names


def _enum_definition_signature(info: EnumInfo) -> tuple[object, ...]:
    return (
        tuple((value.name, value.value) for value in info.enumerators),
        info.scoped,
        info.fixed_base_evidence,
        info.representation_type,
        info.byte_size,
        info.defining_alias,
    )

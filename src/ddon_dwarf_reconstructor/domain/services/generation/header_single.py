"""Single-header rendering operations."""

from __future__ import annotations

from ....core.observability import get_logger, log_timing
from ...models.dwarf import ClassInfo
from .alias_rendering import (
    external_alias_lines,
    referenced_namespace_aliases,
    scoped_typedef_line,
)
from .header_guards import header_guard
from .header_hierarchy_support import namespace_for_info
from .rendering.operations import HeaderRenderingHost
from .template_declarations import primary_declaration
from .template_forward_declarations import ensure_family_plans, planned_template_forwards

logger = get_logger(__name__)


def _scoped_definition(info: ClassInfo, lines: list[str]) -> list[str]:
    namespace = namespace_for_info(info)
    result = [f"namespace {namespace} {{", *lines, "}"] if namespace else list(lines)
    return [*result, *external_alias_lines(info.source_aliases)]


def _exclude_alias_forwards(
    renderer: HeaderRenderingHost,
    declarations: set[str],
    class_info: ClassInfo,
    typedefs: dict[str, str],
) -> set[str]:
    alias_names = {
        alias.name for alias in referenced_namespace_aliases((class_info,), typedefs).values()
    }
    return {
        declaration
        for declaration in declarations
        if renderer._forward_declaration_name(declaration) not in alias_names
    }


class SingleHeaderGenerationService:
    @log_timing
    def generate_header(
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        typedefs: dict[str, str] | None = None,
        cu_offset: int | None = None,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header for a single class.

        Args:
            class_info: ClassInfo object to generate header for
            typedefs: Dictionary of typedef name -> underlying type
            cu_offset: Compilation unit offset for metadata
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        class_info = ensure_family_plans({class_info.name: class_info})[class_info.name]
        class_name = class_info.name
        guard = header_guard(class_info.qualified_name or class_name)
        lines = [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <cstdint>",
            "",
        ]

        lines.extend(self._single_typedef_lines(typedefs, class_info))

        if include_metadata:
            lines.extend(self._generate_metadata_header(class_info, cu_offset))

        lines.extend(self._single_forward_declaration_lines(class_info, typedefs))

        # Generate class definition
        class_lines = self._generate_single_class(class_info, include_metadata)
        lines.extend([""] + _scoped_definition(class_info, class_lines))

        lines.extend(["", f"#endif // {guard}"])

        return "\n".join(lines)

    def _single_typedef_lines(
        self: HeaderRenderingHost, typedefs: dict[str, str] | None, class_info: ClassInfo
    ) -> list[str]:
        lines: list[str] = []
        typedef_map = typedefs or {}
        typedef_forward_decls = _exclude_alias_forwards(
            self, self._collect_typedef_forward_declarations(typedef_map), class_info, typedef_map
        )
        if typedef_forward_decls:
            lines.extend(
                [
                    "// Forward declarations",
                    *sorted(typedef_forward_decls, key=self._forward_declaration_order),
                    "",
                ]
            )
        if not typedefs:
            return lines
        namespace_aliases = referenced_namespace_aliases((class_info,), typedefs)
        lines.append("// Type definitions from DWARF")
        for typedef_name, underlying_type in self._ordered_typedefs(typedefs):
            if self._normalize_type_name(underlying_type) == typedef_name:
                continue
            if typedef_name == "size_t":
                lines.append("// size_t provided by the standard C++ headers")
                continue
            rendered_type = self._void_alias_storage_type(underlying_type)
            if "::*" in rendered_type:
                declaration = f"using {typedef_name} = {rendered_type};"
            else:
                declaration = f"typedef {rendered_type} {typedef_name};"
            lines.append(scoped_typedef_line(declaration, namespace_aliases.get(typedef_name)))
        lines.append("")
        return lines

    def _single_forward_declaration_lines(
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        typedefs: dict[str, str] | None,
    ) -> list[str]:
        forward_decls = _exclude_alias_forwards(
            self,
            self._collect_forward_declarations(class_info, typedefs or {}),
            class_info,
            typedefs or {},
        )
        infos = {class_info.name: class_info}
        forward_decls = planned_template_forwards(self, forward_decls, infos, infos)
        if not forward_decls:
            return []
        return [
            "",
            "// Forward declarations",
            *sorted(forward_decls, key=self._forward_declaration_order),
        ]

    @log_timing
    def generate_single_class_header(
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        class_dependencies: dict[str, str] | None = None,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header for single class with include dependencies (multi-file mode).

        This method generates a standalone header for one class with #include statements
        for dependency headers instead of forward declarations. Each include statement
        references the header file where the dependency is defined.

        Args:
            class_info: ClassInfo for the target class
            class_dependencies: Dict mapping class names to their header filenames
                                (e.g., {"MtObject": "MtObject.h"})
            typedefs: Dictionary of typedef name -> underlying type
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file with includes and class definition
        """
        class_info = ensure_family_plans({class_info.name: class_info})[class_info.name]
        class_name = class_info.name
        guard = header_guard(class_info.qualified_name or class_name)
        lines = self._single_class_header_prefix(guard)
        primary = primary_declaration(class_info)
        if primary is not None:
            lines.append(primary)
        lines.extend(self._dependency_include_lines(class_name, class_dependencies))
        lines.extend(self._base_class_include_lines(class_info, class_dependencies))
        lines.extend(self._typedef_block(typedefs))
        if include_metadata:
            lines.extend(self._single_class_metadata_lines(class_info))

        # Generate class definition (no forward declarations - all includes above)
        class_lines = self._generate_single_class(class_info, include_metadata=False)
        lines.extend(_scoped_definition(class_info, class_lines))

        # Close include guard
        lines.extend(["", f"#endif // {guard}"])

        return "\n".join(lines)

    @staticmethod
    def _single_class_header_prefix(guard: str) -> list[str]:
        return [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <cstdint>",
            "",
        ]

    @staticmethod
    def _dependency_include_lines(
        class_name: str,
        class_dependencies: dict[str, str] | None,
    ) -> list[str]:
        if not class_dependencies:
            return []
        headers = {
            header
            for dependency, header in class_dependencies.items()
            if dependency != class_name and header
        }
        if not headers:
            return []
        return ["// Dependencies", *[f'#include "{header}"' for header in sorted(headers)], ""]

    @staticmethod
    def _base_class_include_lines(
        class_info: ClassInfo,
        class_dependencies: dict[str, str] | None,
    ) -> list[str]:
        if not class_dependencies:
            return []
        headers = {
            class_dependencies[base_name]
            for base_name in class_info.base_classes
            if class_dependencies.get(base_name)
        }
        if not headers:
            return []
        return ["// Base classes", *[f'#include "{header}"' for header in sorted(headers)], ""]

    def _typedef_block(self: HeaderRenderingHost, typedefs: dict[str, str] | None) -> list[str]:
        if not typedefs:
            return []
        lines = ["// Type definitions"]
        for typedef_name, underlying_type in self._ordered_typedefs(typedefs):
            if self._normalize_type_name(underlying_type) == typedef_name:
                continue
            if typedef_name == "size_t":
                lines.append("// size_t provided by the standard C++ headers")
            else:
                rendered_type = self._void_alias_storage_type(underlying_type)
                if "::*" in rendered_type:
                    lines.append(f"using {typedef_name} = {rendered_type};")
                else:
                    lines.append(f"typedef {rendered_type} {typedef_name};")
        lines.append("")
        return lines

    def _void_alias_storage_type(self: HeaderRenderingHost, underlying_type: str) -> str:
        """Give exact-void handle aliases a declaration-safe storage type."""
        if self._normalize_type_name(underlying_type) == "void":
            return "std::uint8_t"
        return self._unqualify_type_expression(underlying_type)

    @staticmethod
    def _single_class_metadata_lines(class_info: ClassInfo) -> list[str]:
        lines = [
            f"// Class: {class_info.name}",
            f"// Size: {class_info.byte_size} bytes",
            f"// DIE Offset: 0x{class_info.die_offset:08x}"
            if class_info.die_offset is not None
            else "// DIE Offset: unknown",
        ]
        if class_info.packing_info:
            lines.append(
                f"// Suggested Packing: {class_info.packing_info.get('suggested_packing', 'unknown')} bytes"
            )
        if class_info.declaration_file:
            lines.append(f"// Declared in: {class_info.declaration_file}")
        lines.append("")
        return lines

    def _generate_metadata_header(
        self: HeaderRenderingHost, class_info: ClassInfo, cu_offset: int | None
    ) -> list[str]:
        """Generate metadata comment block for class."""
        lines = [
            "// Generated from DWARF debug information using pyelftools",
            f"// Target symbol: {class_info.name}",
            "",
            "// DWARF Debug Information:",
            f"// - Size: {class_info.byte_size} bytes",
            "// - DIE Offset: "
            + (
                f"0x{class_info.die_offset:08x}"
                if class_info.die_offset is not None
                else "unavailable"
            ),
        ]

        if cu_offset is not None:
            lines.append(f"// - Source CU: 0x{cu_offset:08x}")

        if class_info.alignment:
            lines.append(f"// - Alignment: {class_info.alignment} bytes")

        if class_info.packing_info:
            packing = class_info.packing_info
            lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")
            if packing["total_padding"] > 0:
                lines.append(f"// - Total Padding: {packing['total_padding']} bytes")

        if class_info.declaration_file:
            lines.append(f"// - Declaration: {class_info.declaration_file}")
            if class_info.declaration_line:
                lines.append(f"// - Line: {class_info.declaration_line}")

        if class_info.base_classes:
            inheritance_chain = " -> ".join(class_info.base_classes) + f" -> {class_info.name}"
            lines.append(f"// - Direct Inheritance: {inheritance_chain}")

        lines.append("")
        return lines

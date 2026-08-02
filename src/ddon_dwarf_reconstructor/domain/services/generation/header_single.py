"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....infrastructure.logging import get_logger, log_timing
from ....utils.path_utils import sanitize_for_filesystem
from ...models.dwarf import ClassInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class SingleHeaderGenerationMixin:
    @log_timing
    def generate_header(
        self: HeaderGeneratorContext,
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
        class_name = class_info.name
        sanitized_name = sanitize_for_filesystem(class_name).upper()
        lines = [
            f"#ifndef {sanitized_name}_H",
            f"#define {sanitized_name}_H",
            "",
            "#include <cstdint>",
            "",
        ]

        typedef_forward_decls = self._collect_typedef_forward_declarations(typedefs or {})
        if typedef_forward_decls:
            lines.append("// Forward declarations")
            lines.extend(sorted(typedef_forward_decls))
            lines.append("")

        # Add typedefs if provided
        if typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in sorted(typedefs.items()):
                if typedef_name == "size_t":
                    lines.append("// size_t provided by the standard C++ headers")
                    continue
                lines.append(f"typedef {underlying_type} {typedef_name};")
            lines.append("")

        if include_metadata:
            lines.extend(self._generate_metadata_header(class_info, cu_offset))

        # Add forward declarations
        forward_decls = self._collect_forward_declarations(class_info, typedefs or {})
        if forward_decls:
            lines.append("")
            lines.append("// Forward declarations")
            for decl in sorted(forward_decls):
                lines.append(decl)

        # Generate class definition
        class_lines = self._generate_single_class(class_info, include_metadata)
        lines.extend([""] + class_lines)

        lines.extend(["", f"#endif // {sanitized_name}_H"])

        return "\n".join(lines)

    @log_timing
    def generate_single_class_header(
        self: HeaderGeneratorContext,
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
        class_name = class_info.name
        sanitized_class = sanitize_for_filesystem(class_name).upper()
        lines = self._single_class_header_prefix(sanitized_class)
        lines.extend(self._dependency_include_lines(class_name, class_dependencies))
        lines.extend(self._base_class_include_lines(class_info, class_dependencies))
        lines.extend(self._typedef_block(typedefs))
        if include_metadata:
            lines.extend(self._single_class_metadata_lines(class_info))

        # Generate class definition (no forward declarations - all includes above)
        class_lines = self._generate_single_class(class_info, include_metadata=False)
        lines.extend(class_lines)

        # Close include guard
        lines.extend(["", f"#endif // {sanitized_class}_H"])

        return "\n".join(lines)

    @staticmethod
    def _single_class_header_prefix(sanitized_class: str) -> list[str]:
        return [
            f"#ifndef {sanitized_class}_H",
            f"#define {sanitized_class}_H",
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
            if base_name in class_dependencies and class_dependencies[base_name]
        }
        if not headers:
            return []
        return ["// Base classes", *[f'#include "{header}"' for header in sorted(headers)], ""]

    @staticmethod
    def _typedef_block(typedefs: dict[str, str] | None) -> list[str]:
        if not typedefs:
            return []
        lines = ["// Type definitions"]
        for typedef_name, underlying_type in sorted(typedefs.items()):
            if typedef_name == "size_t":
                lines.append("// size_t provided by the standard C++ headers")
            else:
                lines.append(f"typedef {underlying_type} {typedef_name};")
        lines.append("")
        return lines

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
        self: HeaderGeneratorContext, class_info: ClassInfo, cu_offset: int | None
    ) -> list[str]:
        """Generate metadata comment block for class."""
        lines = [
            "// Generated from DWARF debug information using pyelftools",
            f"// Target symbol: {class_info.name}",
            "",
            "// DWARF Debug Information:",
            f"// - Size: {class_info.byte_size} bytes",
            f"// - DIE Offset: 0x{class_info.die_offset:08x}",
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

"""Aggregate member rendering operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import EnumInfo, StructInfo, UnionInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HeaderAggregateRenderingMixin:
    def _generate_enum_definition(
        self: HeaderGeneratorContext, enum: EnumInfo, include_metadata: bool
    ) -> list[str]:
        """Generate enum definition."""
        lines = []

        if include_metadata:
            lines.append(f"    // Enum {enum.name} ({enum.byte_size} bytes)")
            if hasattr(enum, "declaration_file") and enum.declaration_file:
                lines.append(f"    // Declared in: {enum.declaration_file}")
                if hasattr(enum, "declaration_line") and enum.declaration_line:
                    lines.append(f"    //   Line: {enum.declaration_line}")

        lines.append(f"    enum class {enum.name}")
        lines.append("    {")

        for i, enumerator in enumerate(enum.enumerators):
            comma = "," if i < len(enum.enumerators) - 1 else ""
            lines.append(f"        {enumerator.name} = {enumerator.value}{comma}")

        lines.append("    };")
        lines.append("")
        return lines

    def _generate_struct_definition(self: HeaderGeneratorContext, struct: StructInfo) -> list[str]:
        """Generate struct definition."""
        struct_name = struct.name if struct.name else "anonymous_struct"
        lines = [
            f"    // Struct {struct_name} ({struct.byte_size} bytes)",
            f"    struct {struct_name}",
            "    {",
        ]

        # Sort members by offset
        sorted_members = sorted(
            [m for m in struct.members if m.offset is not None],
            key=lambda m: m.offset,
        )

        for member in sorted_members:
            declaration = self._format_member_declaration(member)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"        {declaration};{offset_comment}")

        lines.extend(["    };", ""])
        return lines

    def _generate_union_definition(self: HeaderGeneratorContext, union: UnionInfo) -> list[str]:
        """Generate union definition."""
        union_name = union.name if union.name else ""
        lines = [
            f"    // Union {union_name} ({union.byte_size} bytes)",
            f"    union {union_name}" if union_name else "    union",
            "    {",
        ]
        lines.extend(self._render_union_nested_structs(union))
        lines.extend(self._render_union_members(union))
        lines.extend(["    };", ""])
        return lines

    def _render_union_nested_structs(self: HeaderGeneratorContext, union: UnionInfo) -> list[str]:
        lines: list[str] = []
        for struct in union.nested_structs:
            lines.extend(self._render_union_struct(struct))
        return lines

    def _render_union_struct(self: HeaderGeneratorContext, struct: StructInfo) -> list[str]:
        struct_name = f" {struct.name}" if struct.name else ""
        lines = [f"        struct{struct_name}", "        {"]
        for member in struct.members:
            declaration = self._format_member_declaration(member)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"            {declaration};{offset_comment}")
        lines.append(f"        }}{f' {struct.name}' if struct.name else ''};")
        return lines

    def _render_union_members(self: HeaderGeneratorContext, union: UnionInfo) -> list[str]:
        lines: list[str] = []
        for member in union.members:
            if not member.name:
                continue
            declaration = self._format_member_declaration(member)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"        {declaration};{offset_comment}")
        return lines

"""Aggregate member rendering operations."""

from __future__ import annotations

from dataclasses import replace
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

        enum_name = (
            "" if enum.name == "unknown_enum" else self._unqualify_type_expression(enum.name)
        )
        lines.append(f"    enum{' class ' + enum_name if enum_name else ''}")
        lines.append("    {")

        for i, enumerator in enumerate(enum.enumerators):
            comma = "," if i < len(enum.enumerators) - 1 else ""
            lines.append(f"        {enumerator.name} = {enumerator.value}{comma}")

        lines.append("    };")
        lines.append("")
        return lines

    def _generate_struct_definition(
        self: HeaderGeneratorContext,
        struct: StructInfo,
        containing_class_name: str | None = None,
        rendered_name: str | None = None,
    ) -> list[str]:
        """Generate struct definition."""
        struct_name = rendered_name or (
            self._unqualify_type_expression(struct.name) if struct.name else "anonymous_struct"
        )
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
            declaration = self._format_member_declaration(member, containing_class_name)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"        {declaration};{offset_comment}")

        lines.extend(["    };", ""])
        return lines

    def _generate_union_definition(
        self: HeaderGeneratorContext,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]:
        """Generate union definition."""
        union_name = union.name if union.name else ""
        lines = [
            f"    // Union {union_name} ({union.byte_size} bytes)",
            f"    union {union_name}" if union_name else "    union",
            "    {",
        ]
        lines.extend(self._render_union_nested_structs(union, containing_class_name))
        lines.extend(
            self._render_union_members(union, containing_class_name, occupied_member_names)
        )
        lines.extend(["    };", ""])
        return lines

    def _render_union_nested_structs(
        self: HeaderGeneratorContext,
        union: UnionInfo,
        containing_class_name: str | None = None,
    ) -> list[str]:
        lines: list[str] = []
        named_structs = [struct for struct in union.nested_structs if struct.name]
        if named_structs:
            for struct in named_structs:
                assert struct.name is not None
                lines.append(f"        struct {self._unqualify_type_expression(struct.name)};")
        for struct in self._ordered_structs(union.nested_structs):
            lines.extend(self._render_union_struct(struct, containing_class_name))
        return lines

    def _render_union_struct(
        self: HeaderGeneratorContext,
        struct: StructInfo,
        containing_class_name: str | None = None,
    ) -> list[str]:
        struct_name = f" {self._unqualify_type_expression(struct.name)}" if struct.name else ""
        lines = [f"        struct{struct_name}", "        {"]
        for member in struct.members:
            declaration = self._format_member_declaration(member, containing_class_name)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"            {declaration};{offset_comment}")
        rendered_name = self._unqualify_type_expression(struct.name) if struct.name else ""
        lines.append(f"        }}{f' {rendered_name}' if rendered_name else ''};")
        return lines

    def _render_union_members(
        self: HeaderGeneratorContext,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]:
        lines: list[str] = []
        used_names = set(occupied_member_names or ())
        for member in union.members:
            if not member.name:
                continue
            member_name = member.name
            if member_name in used_names:
                member_name = f"{member_name}__union"
                suffix = 2
                while member_name in used_names:
                    member_name = f"{member.name}__union_{suffix}"
                    suffix += 1
            used_names.add(member_name)
            rendered_member = replace(member, name=member_name)
            declaration = self._format_member_declaration(rendered_member, containing_class_name)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            rename_comment = (
                f"  // original DWARF name: {member.name}" if member_name != member.name else ""
            )
            lines.append(f"        {declaration};{offset_comment}{rename_comment}")
        return lines

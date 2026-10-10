"""Aggregate member rendering operations."""

from __future__ import annotations

from dataclasses import replace

from ....core.observability import get_logger
from ...models.dwarf import EnumInfo, MemberInfo, StructInfo, UnionInfo
from .enum_declarations import enum_definition_lines
from .rendering.operations import HeaderRenderingHost

logger = get_logger(__name__)


def _enum_metadata(enum: EnumInfo, include_metadata: bool) -> list[str]:
    if not include_metadata:
        return []
    size = str(enum.byte_size) if enum.byte_size is not None else "unavailable"
    lines = [f"    // Enum {enum.name} ({size} bytes)"]
    if enum.declaration_file:
        lines.append(f"    // Declared in: {enum.declaration_file}")
        if enum.declaration_line is not None:
            lines.append(f"    //   Line: {enum.declaration_line}")
    return lines


def _ordered_struct_members(struct: StructInfo) -> list[MemberInfo]:
    """Keep a zero-width alignment barrier in its original declaration position."""
    included = [
        member for member in struct.members if member.offset is not None or member.bit_size == 0
    ]
    if any(member.bit_size == 0 for member in included):
        return included
    return sorted(included, key=lambda member: member.offset or 0)


class HeaderAggregateRenderingService:
    def _generate_enum_definition(
        self: HeaderRenderingHost, enum: EnumInfo, include_metadata: bool
    ) -> list[str]:
        """Generate enum definition."""
        lines = _enum_metadata(enum, include_metadata)

        enum_name = (
            "" if enum.name == "unknown_enum" else self._unqualify_type_expression(enum.name)
        )
        lines.extend(enum_definition_lines(enum, enum_name, indent="    "))
        lines.append("")
        return lines

    def _generate_struct_definition(
        self: HeaderRenderingHost,
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
            "    typedef struct"
            if struct.defining_alias is not None
            else f"    struct {struct_name}",
            "    {",
        ]

        for member in _ordered_struct_members(struct):
            declaration = self._format_member_declaration(member, containing_class_name)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"        {declaration};{offset_comment}")

        ending = f"    }} {struct_name};" if struct.defining_alias is not None else "    };"
        lines.extend([ending, ""])
        return lines

    def _generate_union_definition(
        self: HeaderRenderingHost,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]:
        """Generate union definition."""
        union_name = union.name if union.name else ""
        lines = [
            f"    // Union {union_name} ({union.byte_size} bytes)",
            "    typedef union"
            if union.defining_alias is not None
            else f"    union {union_name}"
            if union_name
            else "    union",
            "    {",
        ]
        lines.extend(self._render_union_nested_structs(union, containing_class_name))
        lines.extend(
            self._render_union_members(union, containing_class_name, occupied_member_names)
        )
        ending = f"    }} {union_name};" if union.defining_alias is not None else "    };"
        lines.extend([ending, ""])
        return lines

    def _render_union_nested_structs(
        self: HeaderRenderingHost,
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
        self: HeaderRenderingHost,
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
        self: HeaderRenderingHost,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]:
        lines: list[str] = []
        used_names = set(occupied_member_names or ())
        for member in union.members:
            if not member.name and member.bit_size != 0:
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

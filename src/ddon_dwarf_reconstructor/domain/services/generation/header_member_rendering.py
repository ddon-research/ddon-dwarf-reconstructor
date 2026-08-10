"""Member rendering operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, MemberInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HeaderMemberRenderingMixin:
    def _format_member_declaration(self: HeaderGeneratorContext, member: MemberInfo) -> str:
        """Format a member declaration with proper C++ syntax.

        Handles special cases like arrays and static members.

        Args:
            member: MemberInfo object to format

        Returns:
            Properly formatted C++ member declaration
        """
        if member.inline_struct is not None:
            lines = ["struct {"]
            for nested_member in member.inline_struct.members:
                declaration = self._format_member_declaration(nested_member)
                lines.append(f"    {declaration};")
            lines.append(f"}} {member.name}")
            return "\n".join(lines)
        if member.opaque_storage_size is not None:
            declaration = f"std::uint8_t {member.name}[{member.opaque_storage_size}]"
            return self._with_bitfield(declaration, member)
        array_declaration = self._format_array_member(member)
        if array_declaration is not None:
            return array_declaration
        if member.is_static:
            return self._format_static_member(member)
        if member.name == "":
            return self._with_bitfield(member.type_name, member)
        return self._with_bitfield(f"{member.type_name} {member.name}", member)

    def _format_array_member(self: HeaderGeneratorContext, member: MemberInfo) -> str | None:
        opening = member.type_name.find("[")
        if opening <= 0:
            return None

        base_type = member.type_name[:opening].strip()
        dimensions = member.type_name[opening:]
        cursor = 0
        while cursor < len(dimensions):
            if dimensions[cursor] != "[":
                return None
            closing = dimensions.find("]", cursor + 1)
            if closing < 0:
                return None
            cursor = closing + 1
        if not base_type or cursor != len(dimensions):
            return None
        if member.is_static:
            type_name = self._const_type(base_type, member)
            return self._with_bitfield(f"static {type_name} {member.name}{dimensions}", member)
        return self._with_bitfield(f"{base_type} {member.name}{dimensions}", member)

    def _format_static_member(self: HeaderGeneratorContext, member: MemberInfo) -> str:
        type_name = self._const_type(member.type_name, member)
        value_part = f" = {member.const_value}" if member.const_value is not None else ""
        return self._with_bitfield(f"static {type_name} {member.name}{value_part}", member)

    @staticmethod
    def _const_type(type_name: str, member: MemberInfo) -> str:
        if member.is_const and not type_name.startswith("const "):
            return f"const {type_name}"
        return type_name

    @staticmethod
    def _with_bitfield(declaration: str, member: MemberInfo) -> str:
        """Append a recoverable bitfield width to a member declaration."""
        if member.bit_size is not None:
            return f"{declaration} : {member.bit_size}"
        return declaration

    @staticmethod
    def _template_rendering_info(class_name: str) -> tuple[str, str, str] | None:
        """Return primary name and argument names for a recovered specialization."""
        opening = class_name.find("<")
        if opening <= 0 or not class_name.endswith(">"):
            return None

        primary_name = class_name[:opening].strip()
        argument = class_name[opening + 1 : -1].strip()
        if not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", primary_name):
            return None
        if not argument:
            return None

        short_argument = argument.rsplit("::", 1)[-1].strip()
        return primary_name, argument, short_argument

    @staticmethod
    def _replace_template_argument(line: str, argument: str, short_argument: str) -> str:
        """Substitute a recovered specialization argument with the template parameter."""
        rendered = line.replace(argument, "T")
        if re.fullmatch(r"[A-Za-z_]\w*", short_argument):
            rendered = re.sub(rf"\b{re.escape(short_argument)}\b", "T", rendered)
        return rendered

    def _generate_single_class(
        self: HeaderGeneratorContext, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        """Generate a single class definition."""
        class_name = class_info.name
        template_info = self._template_rendering_info(class_name)
        declaration_name = template_info[0] if template_info else class_name
        lines = self._class_header_lines(
            class_info, include_metadata, template_info, declaration_name
        )
        lines.extend(self._nested_type_lines(class_info, include_metadata))
        lines.extend(self._method_lines(class_info, class_name))
        lines.extend(self._member_lines(class_info))
        lines.append("};")
        if template_info:
            _, argument, short_argument = template_info
            lines = [
                self._replace_template_argument(line, argument, short_argument) for line in lines
            ]
        return lines

    def _class_header_lines(
        self: HeaderGeneratorContext,
        class_info: ClassInfo,
        include_metadata: bool,
        template_info: tuple[str, str, str] | None,
        declaration_name: str,
    ) -> list[str]:
        lines = self._class_metadata_lines(class_info, include_metadata)
        inheritance = (
            f" : public {', public '.join(class_info.base_classes)}"
            if class_info.base_classes
            else ""
        )
        alignment = ""
        if class_info.alignment and class_info.alignment > 1:
            alignment = f" __attribute__((aligned({class_info.alignment})))"
            if include_metadata:
                lines.append(f"// - Alignment: {class_info.alignment} bytes")
        aggregate_kind = (
            class_info.kind if class_info.kind in {"class", "struct", "union"} else "class"
        )
        if template_info:
            lines.append("template <typename T>")
        lines.extend([f"{aggregate_kind}{alignment} {declaration_name}{inheritance}", "{"])
        return lines

    def _class_metadata_lines(
        self: HeaderGeneratorContext, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        if not include_metadata:
            return []
        lines = [
            f"// {class_info.name} - DWARF Information:",
            f"// - Size: {class_info.byte_size} bytes",
            "// - DIE Offset: "
            + (
                f"0x{class_info.die_offset:08x}"
                if class_info.die_offset is not None
                else "unavailable"
            ),
        ]
        if self.class_parser and class_info.name in self.class_parser.timed_out_symbols:
            lines.append(
                "// - WARNING: Type lookup timed out. Definition may be incomplete or missing."
            )
        if class_info.packing_info:
            lines.append(
                f"// - Suggested Packing: {class_info.packing_info['suggested_packing']} bytes"
            )
            if class_info.packing_info["total_padding"] > 0:
                lines.append(
                    f"// - Total Padding: {class_info.packing_info['total_padding']} bytes"
                )
        if class_info.declaration_file:
            lines.append(f"// - Declaration: {class_info.declaration_file}")
            if class_info.declaration_line:
                lines.append(f"//   Line: {class_info.declaration_line}")
        if class_info.base_classes:
            lines.append(f"// - Inherits from: {', '.join(class_info.base_classes)}")
        return lines

    def _nested_type_lines(
        self: HeaderGeneratorContext, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        return [
            *self._enum_lines(class_info, include_metadata),
            *self._struct_lines(class_info),
            *self._nested_class_lines(class_info),
            *self._union_lines(class_info),
        ]

    def _enum_lines(
        self: HeaderGeneratorContext, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        if not class_info.enums:
            return []
        lines = ["public:"]
        for enum in class_info.enums:
            lines.extend(self._generate_enum_definition(enum, include_metadata))
        return lines

    def _struct_lines(self: HeaderGeneratorContext, class_info: ClassInfo) -> list[str]:
        if not class_info.nested_structs:
            return []
        lines = ["public:"]
        for struct in class_info.nested_structs:
            lines.extend(self._generate_struct_definition(struct))
        return lines

    def _nested_class_lines(self: HeaderGeneratorContext, class_info: ClassInfo) -> list[str]:
        if not class_info.nested_classes:
            return []
        lines = ["public:"]
        for nested_class in class_info.nested_classes:
            nested_lines = self._generate_single_class(nested_class, include_metadata=False)
            lines.extend(f"    {line}" if line else "" for line in nested_lines)
        return lines

    def _union_lines(self: HeaderGeneratorContext, class_info: ClassInfo) -> list[str]:
        if not class_info.unions:
            return []
        lines = ["public:"]
        for union in class_info.unions:
            lines.extend(self._generate_union_definition(union))
        return lines

    def _method_lines(
        self: HeaderGeneratorContext, class_info: ClassInfo, class_name: str
    ) -> list[str]:
        lines: list[str] = []
        for access in ("public", "protected", "private"):
            access_methods = [method for method in class_info.methods if method.access == access]
            if access_methods:
                lines.extend([f"{access}:", *self._generate_methods(access_methods, class_name)])
        return lines

    def _member_lines(self: HeaderGeneratorContext, class_info: ClassInfo) -> list[str]:
        lines: list[str] = []
        for access in ("public", "protected", "private"):
            access_members = [member for member in class_info.members if member.access == access]
            if access_members:
                lines.extend([f"{access}:", *self._render_access_members(access_members)])
        return lines

    def _render_access_members(
        self: HeaderGeneratorContext, members: list[MemberInfo]
    ) -> list[str]:
        lines = []
        for member in [item for item in members if not item.is_static]:
            declaration = self._format_member_declaration(member)
            offset_comment = (
                f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
            )
            lines.append(f"    {declaration};{offset_comment}")
        static_members = [item for item in members if item.is_static]
        if static_members:
            lines.extend(["", "    // Static members"])
            lines.extend(
                f"    {self._format_member_declaration(member)};" for member in static_members
            )
        return lines

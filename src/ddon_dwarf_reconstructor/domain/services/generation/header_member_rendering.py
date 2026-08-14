"""Member rendering operations."""

from __future__ import annotations

import re

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, MemberInfo
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy

logger = get_logger(__name__)


class HeaderMemberRenderingService:
    def _format_member_declaration(
        self: HeaderRenderingHost,
        member: MemberInfo,
        containing_class_name: str | None = None,
    ) -> str:
        """Format a member declaration with proper C++ syntax.

        Handles special cases like arrays and static members.

        Args:
            member: MemberInfo object to format

        Returns:
            Properly formatted C++ member declaration
        """
        type_name = self._unqualify_type_expression(member.type_name)
        if member.inline_struct is not None:
            return self._format_inline_member(member)
        if member.opaque_storage_size is not None:
            return f"std::uint8_t {member.name}[{member.opaque_storage_size}]"
        for declaration in (
            self._recursive_member_storage(member, containing_class_name),
            self._opaque_bitfield_declaration(member, type_name),
            self._format_array_member(member),
        ):
            if declaration is not None:
                return declaration
        return self._format_scalar_member(member, type_name)

    def _format_inline_member(self: HeaderRenderingHost, member: MemberInfo) -> str:
        lines = ["struct {"]
        assert member.inline_struct is not None
        for nested_member in member.inline_struct.members:
            declaration = self._format_member_declaration(nested_member)
            lines.append(f"    {declaration};")
        lines.append(f"}} {member.name}")
        return "\n".join(lines)

    def _format_scalar_member(self: HeaderRenderingHost, member: MemberInfo, type_name: str) -> str:
        if (
            "*" not in type_name
            and "&" not in type_name
            and not self._is_known_render_type(self._normalize_type_name(type_name))
        ):
            declaration = f"std::uint8_t {member.name}"
            return f"static {declaration}" if member.is_static else declaration
        if member.is_static:
            return self._format_static_member(member)
        if member.name == "":
            return self._with_bitfield(type_name, member)
        return self._with_bitfield(f"{type_name} {member.name}", member)

    def _recursive_member_storage(
        self: HeaderRenderingHost,
        member: MemberInfo,
        containing_class_name: str | None,
    ) -> str | None:
        if containing_class_name is None or "*" in member.type_name or "&" in member.type_name:
            return None
        base_type = self._normalize_type_name(member.type_name).split("[", 1)[0].strip()
        if not base_type or self._nested_definition_key(base_type) != self._nested_definition_key(
            containing_class_name
        ):
            return None
        array_suffix = (
            member.type_name[member.type_name.find("[") :] if "[" in member.type_name else ""
        )
        storage_size = member.opaque_storage_size or self._array_storage_size(array_suffix)
        if not array_suffix:
            storage_size = max(1, storage_size)
        return f"std::uint8_t {member.name}[{storage_size}]"

    def _format_array_member(self: HeaderRenderingHost, member: MemberInfo) -> str | None:
        opening = member.type_name.find("[")
        if opening <= 0:
            return None

        base_type = self._unqualify_type_expression(member.type_name[:opening].strip())
        dimensions = member.type_name[opening:]
        if not base_type or not self._valid_array_dimensions(dimensions):
            return None
        if base_type in {"void", "unknown_type", "base_type", "subroutine_type"}:
            return self._opaque_array_member(member, dimensions)
        if not self._is_known_render_type(base_type):
            return self._unknown_array_member(member, base_type, dimensions)
        return self._known_array_member(member, base_type, dimensions)

    @staticmethod
    def _valid_array_dimensions(dimensions: str) -> bool:
        cursor = 0
        while cursor < len(dimensions):
            if dimensions[cursor] != "[":
                return False
            closing = dimensions.find("]", cursor + 1)
            if closing < 0:
                return False
            cursor = closing + 1
        return cursor == len(dimensions)

    def _opaque_array_member(self: HeaderRenderingHost, member: MemberInfo, dimensions: str) -> str:
        storage_size = self._array_storage_size(dimensions)
        rendered = f"std::uint8_t {member.name}[{storage_size}]"
        return f"static {rendered}" if member.is_static else rendered

    def _unknown_array_member(
        self: HeaderRenderingHost, member: MemberInfo, base_type: str, dimensions: str
    ) -> str:
        if "[]" in dimensions:
            rendered = f"{base_type} {member.name}{dimensions}"
            return f"static {rendered}" if member.is_static else rendered
        storage_size = member.opaque_storage_size or self._array_storage_size(dimensions)
        rendered = f"std::uint8_t {member.name}[{storage_size}]"
        return f"static {rendered}" if member.is_static else rendered

    def _known_array_member(
        self: HeaderRenderingHost, member: MemberInfo, base_type: str, dimensions: str
    ) -> str:
        if member.is_static:
            type_name = self._const_type(base_type, member)
            return self._with_bitfield(f"static {type_name} {member.name}{dimensions}", member)
        return self._with_bitfield(f"{base_type} {member.name}{dimensions}", member)

    @staticmethod
    def _array_storage_size(dimensions: str) -> int:
        sizes = [int(value) for value in re.findall(r"\[(\d+)\]", dimensions) if int(value) > 0]
        storage_size = 1
        for size in sizes:
            storage_size *= size
        return storage_size

    def _is_known_render_type(self: HeaderRenderingHost, type_name: str) -> bool:
        if self._is_builtin_type(type_name) or type_name.startswith("std::"):
            return True
        if re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*\s*<.+>", type_name):
            return True
        known_names = self._known_render_type_names
        return type_name in known_names or self._nested_definition_key(type_name) in known_names

    def _format_static_member(self: HeaderRenderingHost, member: MemberInfo) -> str:
        type_name = self._unqualify_type_expression(member.type_name)
        type_name = self._const_type(type_name, member)
        value_part = f" = {member.const_value}" if member.const_value is not None else ""
        if member.const_value is not None:
            value_part = f" = {self._enum_static_initializer(type_name, member.const_value)}"
        return self._with_bitfield(f"static {type_name} {member.name}{value_part}", member)

    @classmethod
    def _enum_static_initializer(cls, type_name: str, value: int) -> str:
        """Cast recovered numeric values for scoped enum-like static members."""
        base_name = re.sub(r"^const\s+", "", type_name).strip()
        if re.fullmatch(r"[A-Za-z_]\w*", base_name) and not cls._is_integral_type(base_name):
            return f"static_cast<{base_name}>({value})"
        return str(value)

    @staticmethod
    def _is_integral_type(type_name: str) -> bool:
        return TypeExpressionPolicy.is_integral(type_name)

    @classmethod
    def _opaque_bitfield_declaration(cls, member: MemberInfo, type_name: str) -> str | None:
        if member.bit_size is None or member.bit_size <= 0 or cls._is_integral_type(type_name):
            return None
        storage_size = max(1, (member.bit_size + 7) // 8)
        member_name = member.name or f"__opaque_bitfield_{member.offset or 0:x}"
        return f"std::uint8_t {member_name}[{storage_size}]"

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

    def _template_rendering_info(
        self: HeaderRenderingHost, class_name: str
    ) -> tuple[str, str, str] | None:
        """Return primary name and argument names for a recovered specialization."""
        opening = class_name.find("<")
        if opening <= 0 or not class_name.endswith(">"):
            return None

        primary_name = self._unqualify_type_expression(class_name[:opening].strip())
        argument = class_name[opening + 1 : -1].strip()
        if not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", primary_name):
            return None
        if not argument:
            return None

        short_argument = (
            "N0"
            if re.fullmatch(r"[-+]?\d+|true|false", argument)
            else argument.rsplit("::", 1)[-1].strip()
        )
        return primary_name, argument, short_argument

    @staticmethod
    def _replace_template_argument(line: str, argument: str, short_argument: str) -> str:
        """Substitute a recovered specialization argument with the template parameter."""
        if re.fullmatch(r"[-+]?\d+|true|false", argument):
            rendered = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(argument)}(?![A-Za-z0-9_])",
                short_argument,
                line,
            )
        else:
            rendered = line.replace(argument, short_argument)
        specialized_short = argument.rsplit("::", 1)[-1].strip()
        if "::" in argument and re.fullmatch(r"[A-Za-z_]\w*", specialized_short):
            rendered = re.sub(rf"\b{re.escape(specialized_short)}\b", short_argument, rendered)
        return rendered

    def _generate_single_class(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
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
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        include_metadata: bool,
        template_info: tuple[str, str, str] | None,
        declaration_name: str,
    ) -> list[str]:
        lines = self._class_metadata_lines(class_info, include_metadata)
        base_names = self._rendered_base_names(class_info)
        inheritance = f" : public {', public '.join(base_names)}" if base_names else ""
        alignment = ""
        if class_info.alignment and class_info.alignment > 1:
            alignment = f" __attribute__((aligned({class_info.alignment})))"
            if include_metadata:
                lines.append(f"// - Alignment: {class_info.alignment} bytes")
        aggregate_kind = (
            class_info.kind if class_info.kind in {"class", "struct", "union"} else "class"
        )
        if template_info:
            lines.append(
                self._template_parameter_declaration(class_info.name) or "template <typename T>"
            )
        lines.extend([f"{aggregate_kind}{alignment} {declaration_name}{inheritance}", "{"])
        return lines

    def _rendered_base_names(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        """Render nested base types with their containing aggregate qualification."""
        qualified_names = self._base_type_names
        return [
            qualified_names.get(offset) or self._unqualify_type_expression(base_name)
            if offset is not None
            else self._unqualify_type_expression(base_name)
            for base_name, offset in zip(
                class_info.base_classes,
                class_info.base_class_offsets,
                strict=False,
            )
        ] + [
            self._unqualify_type_expression(base_name)
            for base_name in class_info.base_classes[len(class_info.base_class_offsets) :]
        ]

    def _class_metadata_lines(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
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

    def _method_lines(
        self: HeaderRenderingHost, class_info: ClassInfo, class_name: str
    ) -> list[str]:
        lines: list[str] = []
        methods = self._deduplicate_rendered_methods(self._deduplicate_methods(class_info.methods))
        for access in ("public", "protected", "private"):
            access_methods = [method for method in methods if method.access == access]
            if access_methods:
                lines.extend([f"{access}:", *self._generate_methods(access_methods, class_name)])
        return lines

    def _member_lines(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        lines: list[str] = []
        for access in ("public", "protected", "private"):
            access_members = [member for member in class_info.members if member.access == access]
            if access_members:
                lines.extend(
                    [
                        f"{access}:",
                        *self._render_access_members(access_members, class_info.name),
                    ]
                )
        return lines

    def _render_access_members(
        self: HeaderRenderingHost,
        members: list[MemberInfo],
        containing_class_name: str | None = None,
    ) -> list[str]:
        lines = []
        for member in [item for item in members if not item.is_static]:
            declaration = self._format_member_declaration(member, containing_class_name)
            offset_comment = (
                f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
            )
            lines.append(f"    {declaration};{offset_comment}")
        static_members = [item for item in members if item.is_static]
        if static_members:
            lines.extend(["", "    // Static members"])
            lines.extend(
                f"    {self._format_member_declaration(member, containing_class_name)};"
                for member in static_members
            )
        return lines

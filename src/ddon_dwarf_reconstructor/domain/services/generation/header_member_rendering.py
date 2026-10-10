"""Member rendering operations."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, MemberInfo, MethodInfo
from ...models.dwarf.template_rendering import TemplateRendering
from ...models.dwarf.type_reference import TypeDeclarator, TypeReference
from .header_type_planning import HeaderTypePlanningService
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy
from .template_declarations import project_template
from .template_families import plan_template_families

logger = get_logger(__name__)


def _qualify_explicit_specialization_types(class_info: ClassInfo) -> ClassInfo:
    """Restore qualified specialization arguments in observed member types.

    DWARF often records a specialization's methods in the lexical scope of
    the primary template, so ``rTbl2<rAcquirement::cAbilityData>`` may carry
    ``cAbilityData*`` method types.  Rendering those names in the standalone
    specialization header would bind a different global type (or fail to
    compile).  Qualify only unqualified occurrences of a qualified template
    argument; concrete evidence remains untouched on the original object.
    """
    mappings = _qualified_template_argument_mappings(class_info.qualified_name or class_info.name)
    if not mappings:
        return class_info

    def qualify(value: str) -> str:
        return _qualify_argument_tokens(value, mappings)

    methods = [_qualify_method(method, qualify) for method in class_info.methods]
    members = [_qualify_member(member, qualify) for member in class_info.members]
    bases = [qualify(base) for base in class_info.base_classes]
    if (
        methods == class_info.methods
        and members == class_info.members
        and bases == class_info.base_classes
    ):
        return class_info
    return replace(class_info, methods=methods, members=members, base_classes=bases)


def _qualify_method(method: MethodInfo, qualify: Callable[[str], str]) -> MethodInfo:
    return replace(
        method,
        return_type=qualify(method.return_type),
        parameters=[
            replace(parameter, type_name=qualify(parameter.type_name))
            for parameter in method.parameters or []
        ],
    )


def _qualify_member(member: MemberInfo, qualify: Callable[[str], str]) -> MemberInfo:
    return replace(member, type_name=qualify(member.type_name))


def _qualified_template_argument_mappings(class_name: str) -> tuple[tuple[str, str], ...]:
    opening = class_name.find("<")
    if opening < 0 or not class_name.endswith(">"):
        return ()
    arguments = HeaderTypePlanningService._split_template_arguments(class_name[opening + 1 : -1])
    mappings: list[tuple[str, str]] = []
    for argument in arguments:
        candidate = argument.strip()
        if "::" not in candidate or not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", candidate):
            continue
        mappings.append((candidate.rsplit("::", 1)[-1], candidate))
    return tuple(sorted(set(mappings), key=lambda item: (-len(item[0]), item[0], item[1])))


def _qualify_argument_tokens(type_name: str, mappings: tuple[tuple[str, str], ...]) -> str:
    result = type_name
    for short_name, qualified_name in mappings:
        result = re.sub(
            rf"(?<![:\w]){re.escape(short_name)}(?!\w)(?!\s*::)",
            qualified_name,
            result,
        )
    return result


class BitfieldDeclarationError(ValueError):
    """DWARF field width cannot be represented by a legal C++ bitfield."""


def _legal_bitfield_kind(kind: str | None, effective: str) -> bool:
    return kind in {"integral", "enum"} or (
        kind is None and TypeExpressionPolicy.is_integral(effective)
    )


class HeaderMemberRenderingService:
    @staticmethod
    def _strip_containing_class(name: str, containing_class_name: str | None) -> str:
        if not containing_class_name:
            return name
        unqual = containing_class_name.split("::")[-1]
        for prefix in (f"{containing_class_name}::", f"{unqual}::"):
            if name.startswith(prefix):
                return name.removeprefix(prefix)
        return name

    def _format_typed_reference_member(
        self: HeaderRenderingHost,
        member: MemberInfo,
        type_ref: TypeReference,
        containing_class_name: str | None,
    ) -> str:
        decl = type_ref.declarator
        stripped_base = self._strip_containing_class(decl.base_name, containing_class_name)
        if stripped_base != decl.base_name:
            decl = replace(decl, base_name=stripped_base)
        declaration = decl.render(member.name)
        if member.is_static:
            declaration = f"static {declaration}"
            if member.const_value is not None:
                declaration += (
                    f" = {self._enum_static_initializer(decl.base_name, member.const_value)}"
                )
        return self._with_bitfield(declaration, member, decl.base_name)

    def _format_member_declaration(
        self: HeaderRenderingHost,
        member: MemberInfo,
        containing_class_name: str | None = None,
        preserve_qualified: bool = False,
    ) -> str:
        """Format a member declaration with proper C++ syntax.

        Handles special cases like arrays and static members.

        Args:
            member: MemberInfo object to format

        Returns:
            Properly formatted C++ member declaration
        """
        if member.inline_struct is not None:
            return self._format_inline_member(member, preserve_qualified)
        if isinstance(member.type_reference, TypeReference):
            return self._format_typed_reference_member(
                member, member.type_reference, containing_class_name
            )
        if member.opaque_storage_size is not None:
            if (
                member.bit_size is not None
                and member.bitfield_base_kind != "member_pointer_storage"
                and self._effective_bitfield_type(member, member.type_name)
            ):
                raise BitfieldDeclarationError(f"opaque bitfield storage: {member.name}")
            return f"std::uint8_t {member.name}[{member.opaque_storage_size}]"
        type_name = self._strip_containing_class(member.type_name, containing_class_name)
        if not preserve_qualified:
            type_name = self._unqualify_type_expression(type_name)
        for declaration in (
            self._recursive_member_storage(member, containing_class_name),
            self._format_array_member(member, preserve_qualified),
        ):
            if declaration is not None:
                return declaration
        return self._format_scalar_member(member, type_name, preserve_qualified)

    def _format_inline_member(
        self: HeaderRenderingHost, member: MemberInfo, preserve_qualified: bool = False
    ) -> str:
        lines = ["struct {"]
        assert member.inline_struct is not None
        for nested_member in member.inline_struct.members:
            declaration = self._format_member_declaration(
                nested_member, preserve_qualified=preserve_qualified
            )
            lines.append(f"    {declaration};")
        lines.append(f"}} {member.name}")
        return "\n".join(lines)

    def _format_scalar_member(
        self: HeaderRenderingHost,
        member: MemberInfo,
        type_name: str,
        preserve_qualified: bool = False,
    ) -> str:
        if (
            "*" not in type_name
            and "&" not in type_name
            and not self._is_known_render_type(self._normalize_type_name(type_name))
        ):
            if member.opaque_storage_size:
                declaration = f"std::uint8_t {member.name}[{member.opaque_storage_size}]"
            elif type_name in {"void", "unknown_type", "base_type", "subroutine_type"}:
                declaration = f"std::uint8_t {member.name}"
            else:
                declaration = f"{type_name} {member.name}"
            formatted = f"static {declaration}" if member.is_static else declaration
            return self._with_bitfield(formatted, member, type_name)
        if member.is_static:
            return self._with_bitfield(
                self._format_static_member(member, preserve_qualified), member, type_name
            )
        if member.name == "":
            return self._with_bitfield(type_name, member, type_name)
        return self._with_bitfield(f"{type_name} {member.name}", member, type_name)

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

    def _format_array_member(
        self: HeaderRenderingHost, member: MemberInfo, preserve_qualified: bool = False
    ) -> str | None:
        opening = member.type_name.find("[")
        if opening <= 0:
            return None

        base_type = member.type_name[:opening].strip()
        if not preserve_qualified:
            base_type = self._unqualify_type_expression(base_type)
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
        if member.opaque_storage_size:
            rendered = f"std::uint8_t {member.name}[{member.opaque_storage_size}]"
            return f"static {rendered}" if member.is_static else rendered
        rendered = f"{base_type} {member.name}{dimensions}"
        return f"static {rendered}" if member.is_static else rendered

    def _known_array_member(
        self: HeaderRenderingHost, member: MemberInfo, base_type: str, dimensions: str
    ) -> str:
        if member.is_static:
            type_name = self._const_type(base_type, member)
            return f"static {type_name} {member.name}{dimensions}"
        return f"{base_type} {member.name}{dimensions}"

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

    def _format_static_member(
        self: HeaderRenderingHost, member: MemberInfo, preserve_qualified: bool = False
    ) -> str:
        type_name = member.type_name
        if not preserve_qualified:
            type_name = self._unqualify_type_expression(type_name)
        type_name = self._const_type(type_name, member)
        value_part = f" = {member.const_value}" if member.const_value is not None else ""
        if member.const_value is not None:
            value_part = f" = {self._enum_static_initializer(type_name, member.const_value)}"
        return f"static {type_name} {member.name}{value_part}"

    @classmethod
    def _enum_static_initializer(cls, type_name: str, value: int) -> str:
        """Cast recovered numeric values for scoped enum-like static members."""
        base_name = re.sub(r"^const\s+", "", type_name).strip()
        if re.fullmatch(
            r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", base_name
        ) and not cls._is_integral_type(base_name):
            short_name = base_name.split("::")[-1]
            return f"static_cast<{short_name}>({value})"
        return str(value)

    @staticmethod
    def _is_integral_type(type_name: str) -> bool:
        return TypeExpressionPolicy.is_integral(type_name)

    @staticmethod
    def _const_type(type_name: str, member: MemberInfo) -> str:
        if member.is_const and not type_name.startswith("const "):
            return f"const {type_name}"
        return type_name

    @classmethod
    def _has_declarator_indirection(cls, decl: TypeDeclarator) -> bool:
        if decl.pointer_depth > 0 or decl.reference_kind or decl.pointer_to_member_of:
            return True
        if decl.function_parameters is not None or decl.array_dimensions:
            return True
        indirection_kinds = {
            "pointer",
            "reference",
            "rvalue_reference",
            "member_pointer",
            "array",
            "function",
        }
        return any(layer.kind in indirection_kinds for layer in decl.layers)

    @classmethod
    def _effective_bitfield_type(cls, member: MemberInfo, type_name: str | None) -> str | None:
        if isinstance(member.type_reference, TypeReference):
            if cls._has_declarator_indirection(member.type_reference.declarator):
                return None
            effective = member.type_reference.declarator.base_name
        else:
            effective = type_name or member.type_name
        if not effective:
            return None
        stripped = re.sub(r"^(?:const|volatile)\s+", "", effective).strip()
        return None if any(c in stripped for c in ("*", "&", "[", "(")) else stripped

    @classmethod
    def _with_bitfield(
        cls, declaration: str, member: MemberInfo, type_name: str | None = None
    ) -> str:
        """Append a recoverable bitfield width to a member declaration if eligible."""
        width = member.bit_size
        if width is None:
            return declaration
        if member.bitfield_base_kind == "member_pointer_storage":
            return declaration
        effective = cls._effective_bitfield_type(member, type_name)
        if effective is None:
            return declaration  # Pointer/array storage width is not C++ bitfield syntax.
        cls._validate_bitfield(member, effective, width)
        return f"{declaration} : {width}"

    @classmethod
    def _validate_bitfield(cls, member: MemberInfo, effective: str, width: int) -> None:
        if member.is_static or type(width) is not int or width < 0:
            raise BitfieldDeclarationError(f"illegal bitfield width or storage: {member.name}")
        if width == 0 and member.name:
            raise BitfieldDeclarationError(f"named zero-width bitfield: {member.name}")
        if not _legal_bitfield_kind(member.bitfield_base_kind, effective):
            raise BitfieldDeclarationError(f"unproven integral bitfield type: {effective}")
        max_bits = member.bitfield_base_bits or 64
        if width > max_bits:
            raise BitfieldDeclarationError(f"bitfield width exceeds {max_bits}: {member.name}")

    def _generate_single_class(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]:
        """Generate a single class definition."""
        prepared = self._prepare_class_for_rendering(class_info, include_metadata)
        if prepared is None:
            plan = class_info.template_rendering
            return [f"// Incomplete template: {plan.diagnostic}"] if plan is not None else []
        class_info, include_metadata = prepared
        plan = class_info.template_rendering
        class_name = class_info.name
        declaration_name = self._declaration_name(class_info, plan)
        lines = self._class_header_lines(class_info, include_metadata, declaration_name)
        lines.extend(self._nested_type_lines(class_info, include_metadata))
        lines.extend(self._method_lines(class_info, class_name))
        lines.extend(self._member_lines(class_info))
        lines.append(f"}} {declaration_name};" if class_info.defining_alias is not None else "};")
        return lines

    def _prepare_class_for_rendering(
        self: HeaderRenderingHost, class_info: ClassInfo, include_metadata: bool
    ) -> tuple[ClassInfo, bool] | None:
        planned = _ensure_template_plan(class_info)
        plan = planned.template_rendering
        if plan is None or plan.mode == "blocked" or not plan.representative:
            return None if plan is not None else (planned, include_metadata)
        if plan.mode == "generic":
            self._known_render_type_names.update(name for _argument, name in plan.substitutions)
            return project_template(planned), False
        return _qualify_explicit_specialization_types(planned), include_metadata

    def _declaration_name(
        self: HeaderRenderingHost, class_info: ClassInfo, plan: TemplateRendering | None
    ) -> str:
        if plan is not None and plan.mode == "generic":
            return _local_template_name(class_info, plan.primary)
        if plan is not None and plan.mode == "explicit":
            return _local_template_name(class_info, class_info.qualified_name or class_info.name)
        return self._unqualify_type_expression(class_info.name)

    def _class_header_lines(
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        include_metadata: bool,
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
        plan = class_info.template_rendering
        if plan is not None:
            lines.append(plan.declaration if plan.mode == "generic" else "template <>")
        declaration = f"{aggregate_kind}{alignment} {declaration_name}{inheritance}"
        if class_info.defining_alias is not None:
            declaration = f"typedef {aggregate_kind}{alignment}{inheritance}"
        lines.extend([declaration, "{"])
        return lines

    def _rendered_base_names(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        """Render nested base types with their containing aggregate qualification."""
        qualified_names = self._base_type_names
        return [
            qualified_names.get((class_info.cu_offset, offset)) or base_name
            if offset is not None
            else base_name
            for base_name, offset in zip(
                class_info.base_classes,
                class_info.base_class_offsets,
                strict=False,
            )
        ] + class_info.base_classes[len(class_info.base_class_offsets) :]

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
        preserve_qualified = (
            class_info.template_rendering is not None
            and class_info.template_rendering.mode == "explicit"
        )
        for access in ("public", "protected", "private"):
            access_methods = [method for method in methods if method.access == access]
            if access_methods:
                lines.extend(
                    [
                        f"{access}:",
                        *self._generate_methods(
                            access_methods, class_name, preserve_qualified=preserve_qualified
                        ),
                    ]
                )
        return lines

    def _member_lines(self: HeaderRenderingHost, class_info: ClassInfo) -> list[str]:
        lines: list[str] = []
        preserve_qualified = (
            class_info.template_rendering is not None
            and class_info.template_rendering.mode == "explicit"
        )
        for access in ("public", "protected", "private"):
            access_members = [member for member in class_info.members if member.access == access]
            if access_members:
                lines.extend(
                    [
                        f"{access}:",
                        *self._render_access_members(
                            access_members,
                            class_info.name,
                            preserve_qualified=preserve_qualified,
                        ),
                    ]
                )
        return lines

    def _render_access_members(
        self: HeaderRenderingHost,
        members: list[MemberInfo],
        containing_class_name: str | None = None,
        preserve_qualified: bool = False,
    ) -> list[str]:
        lines = []
        for member in [item for item in members if not item.is_static]:
            declaration = self._format_member_declaration(
                member, containing_class_name, preserve_qualified
            )
            offset_comment = (
                f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
            )
            lines.append(f"    {declaration};{offset_comment}")
        static_members = [item for item in members if item.is_static]
        if static_members:
            lines.extend(["", "    // Static members"])
            lines.extend(
                f"    {self._format_member_declaration(member, containing_class_name, preserve_qualified)};"
                for member in static_members
            )
        return lines


def _local_template_name(info: ClassInfo, name: str) -> str:
    if info.scope is not None and info.scope.namespace_only:
        namespace = "::".join(component.name for component in info.scope.components)
        return name.removeprefix(namespace + "::") if namespace else name
    return name


def _ensure_template_plan(info: ClassInfo) -> ClassInfo:
    if "<" not in info.name or info.template_rendering is not None:
        return info
    planned, _families = plan_template_families({info.name: info}, {})
    return planned[info.name]

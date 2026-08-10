"""Typed collaboration contract for header-planning and rendering stages."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from ...models.dwarf import (
    ClassInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
    TypeReference,
    UnionInfo,
)
from ...ports.class_parser import ClassParserPort
from ...ports.dwarf_lookup import DwarfLookupPort


class HeaderTypeReferenceContext(Protocol):
    """Shared type-reference operations used by declaration and ordering stages."""

    def _forward_declaration_name(self, declaration: str) -> str: ...

    def _normalize_type_name(self, type_name: str) -> str: ...

    def _referenced_class_name(self, type_name: str, class_names: set[str]) -> str | None: ...

    def _iter_nested_classes(self, class_info: ClassInfo) -> list[ClassInfo]: ...

    def _aggregate_names(self, class_info: ClassInfo) -> tuple[set[str], set[str], set[str]]: ...

    def _primitive_names(self) -> set[str]: ...

    def _referenced_types(
        self, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _nested_struct_types(
        self, structs: list[StructInfo]
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _union_types(
        self, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _method_types(
        self, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _struct_member_types(
        self, struct: StructInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _template_argument_types(
        self, member: MemberInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _template_reference_types(
        self, reference: TypeReference
    ) -> Iterator[tuple[str | None, int | None, bool]]: ...

    def _add_forward_declaration(
        self,
        declarations: set[str],
        type_name: str | None,
        type_offset: int | None,
        allow_textual_pointer: bool,
        excluded_names: set[str],
        primitives: set[str],
    ) -> None: ...

    def _should_forward_declare(
        self,
        type_name: str | None,
        type_offset: int | None,
        allow_textual_pointer: bool,
        excluded_names: set[str],
        primitives: set[str],
    ) -> bool: ...

    def _is_textual_pointer(self, type_name: str, clean_name: str, allowed: bool) -> bool: ...

    def _aggregate_forward_declaration(self, clean_name: str) -> str | None: ...


class HeaderGeneratorContext(HeaderTypeReferenceContext, Protocol):
    """State and operations shared by deterministic header responsibilities."""

    dwarf_index: DwarfLookupPort
    class_parser: ClassParserPort | None
    _base_type_names: dict[int, str]
    _known_render_type_names: set[str]

    def _qualified_base_type_names(self, class_infos: dict[str, ClassInfo]) -> dict[int, str]: ...

    def _render_type_names(
        self, class_infos: dict[str, ClassInfo], typedefs: dict[str, str]
    ) -> set[str]: ...

    def _forward_declaration_kind(self, name: str) -> str | None: ...

    def _collect_typedef_forward_declarations(self, typedefs: dict[str, str]) -> set[str]: ...

    def _collect_forward_declarations(
        self, class_info: ClassInfo, typedefs: dict[str, str]
    ) -> set[str]: ...

    def _forward_declaration_for_type(
        self, clean_name: str, type_offset: int | None
    ) -> str | None: ...

    def _should_forward_declare_die(
        self, clean_name: str, type_offset: int, excluded_names: set[str]
    ) -> bool: ...

    def _generate_single_class(
        self, class_info: ClassInfo, include_metadata: bool
    ) -> list[str]: ...

    def _generate_metadata_header(
        self, class_info: ClassInfo, cu_offset: int | None
    ) -> list[str]: ...

    def _single_class_header_prefix(self, sanitized_class: str) -> list[str]: ...

    def _dependency_include_lines(
        self, class_name: str, class_dependencies: dict[str, str] | None
    ) -> list[str]: ...

    def _base_class_include_lines(
        self, class_info: ClassInfo, class_dependencies: dict[str, str] | None
    ) -> list[str]: ...

    def _typedef_block(self, typedefs: dict[str, str] | None) -> list[str]: ...

    def _single_typedef_lines(self, typedefs: dict[str, str] | None) -> list[str]: ...

    def _single_forward_declaration_lines(
        self, class_info: ClassInfo, typedefs: dict[str, str] | None
    ) -> list[str]: ...

    def _single_class_metadata_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _void_alias_storage_type(self, underlying_type: str) -> str: ...

    def _format_member_declaration(
        self, member: MemberInfo, containing_class_name: str | None = None
    ) -> str: ...

    def _format_inline_member(self, member: MemberInfo) -> str: ...

    def _format_scalar_member(self, member: MemberInfo, type_name: str) -> str: ...

    @staticmethod
    def _valid_array_dimensions(dimensions: str) -> bool: ...

    def _opaque_array_member(self, member: MemberInfo, dimensions: str) -> str: ...

    def _unknown_array_member(self, member: MemberInfo, base_type: str, dimensions: str) -> str: ...

    def _known_array_member(self, member: MemberInfo, base_type: str, dimensions: str) -> str: ...

    def _format_array_member(self, member: MemberInfo) -> str | None: ...

    def _format_static_member(self, member: MemberInfo) -> str: ...

    def _const_type(self, type_name: str, member: MemberInfo) -> str: ...

    def _with_bitfield(self, declaration: str, member: MemberInfo) -> str: ...

    def _unqualify_type_expression(self, type_name: str) -> str: ...

    def _ordered_typedefs(self, typedefs: dict[str, str]) -> list[tuple[str, str]]: ...

    def _ordered_structs(self, structs: list[StructInfo]) -> list[StructInfo]: ...

    def _template_expressions(self, type_name: str) -> list[str]: ...

    def _template_parameter_declaration(self, type_name: str) -> str | None: ...

    def _template_forward_declaration(self, type_name: str) -> str | None: ...

    def _template_forward_declarations(
        self, clean_name: str, typedef_names: set[str]
    ) -> set[str]: ...

    def _template_argument_forward_declarations(
        self, expression: str, typedef_names: set[str]
    ) -> set[str]: ...

    def _split_template_arguments(self, arguments: str) -> list[str]: ...

    def _is_builtin_type(self, type_name: str) -> bool: ...

    def _replace_template_argument(self, line: str, argument: str, short_argument: str) -> str: ...

    def _template_rendering_info(self, class_name: str) -> tuple[str, str, str] | None: ...

    def _class_header_lines(
        self,
        class_info: ClassInfo,
        include_metadata: bool,
        template_info: tuple[str, str, str] | None,
        declaration_name: str,
    ) -> list[str]: ...

    def _rendered_base_names(self, class_info: ClassInfo) -> list[str]: ...

    def _class_metadata_lines(self, class_info: ClassInfo, include_metadata: bool) -> list[str]: ...

    def _nested_type_lines(self, class_info: ClassInfo, include_metadata: bool) -> list[str]: ...

    def _nested_aggregate_definition_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _ordered_nested_aggregates(
        self, class_info: ClassInfo
    ) -> list[tuple[str, ClassInfo | StructInfo | UnionInfo]]: ...

    def _nested_aggregate_dependencies(
        self,
        kind: str,
        aggregate: ClassInfo | StructInfo | UnionInfo,
        key: str,
        names: set[str],
    ) -> set[str]: ...

    def _nested_aggregate_parts(
        self, kind: str, aggregate: ClassInfo | StructInfo | UnionInfo
    ) -> tuple[list[MemberInfo], list[str]]: ...

    def _nested_type_forward_declarations(self, class_info: ClassInfo) -> list[str]: ...

    def _nested_enum_forward_declarations(self, class_info: ClassInfo) -> list[str]: ...

    def _nested_struct_forward_declarations(self, class_info: ClassInfo) -> list[str]: ...

    def _nested_class_forward_declarations(self, class_info: ClassInfo) -> list[str]: ...

    def _nested_union_forward_declarations(self, class_info: ClassInfo) -> list[str]: ...

    def _enum_lines(self, class_info: ClassInfo, include_metadata: bool) -> list[str]: ...

    def _struct_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _nested_class_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _ordered_nested_classes(self, nested_classes: list[ClassInfo]) -> list[ClassInfo]: ...

    def _nested_class_dependencies(self, class_info: ClassInfo, names: set[str]) -> set[str]: ...

    def _nested_definition_key(self, name: str) -> str: ...

    def _nested_class_richness(self, class_info: ClassInfo) -> int: ...

    def _all_nested_members(self, class_info: ClassInfo) -> list[MemberInfo]: ...

    def _value_typedef_dependency_names(
        self, underlying_type: str, class_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def _typedef_dependency_names(
        self, underlying_type: str, class_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def _value_typedef_underlyings(
        self, class_info: ClassInfo | None, typedefs: dict[str, str]
    ) -> list[str]: ...

    @staticmethod
    def _class_info_for_name(
        class_infos: dict[str, ClassInfo], class_name: str
    ) -> ClassInfo | None: ...

    def _template_specialization_names(self, expression: str, names: set[str]) -> set[str]: ...

    def _referenced_dependency_names(self, type_name: str, names: set[str]) -> set[str]: ...

    def _union_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _method_lines(self, class_info: ClassInfo, class_name: str) -> list[str]: ...

    @staticmethod
    def _canonical_method_name(method_name: str) -> str: ...

    @staticmethod
    def _canonical_parameter_type(parameter: ParameterInfo) -> tuple[object, ...]: ...

    def _member_lines(self, class_info: ClassInfo) -> list[str]: ...

    def _render_access_members(
        self, members: list[MemberInfo], containing_class_name: str | None = None
    ) -> list[str]: ...

    def _recursive_member_storage(
        self, member: MemberInfo, containing_class_name: str | None
    ) -> str | None: ...

    def _is_known_render_type(self, type_name: str) -> bool: ...

    def _generate_enum_definition(self, enum: EnumInfo, include_metadata: bool) -> list[str]: ...

    def _generate_struct_definition(
        self,
        struct: StructInfo,
        containing_class_name: str | None = None,
        rendered_name: str | None = None,
    ) -> list[str]: ...

    def _generate_union_definition(
        self,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]: ...

    def _render_union_nested_structs(
        self, union: UnionInfo, containing_class_name: str | None = None
    ) -> list[str]: ...

    def _render_union_struct(
        self, struct: StructInfo, containing_class_name: str | None = None
    ) -> list[str]: ...

    def _render_union_members(
        self,
        union: UnionInfo,
        containing_class_name: str | None = None,
        occupied_member_names: set[str] | None = None,
    ) -> list[str]: ...

    @staticmethod
    def _member_names(class_info: ClassInfo) -> set[str]: ...

    @staticmethod
    def _array_storage_size(dimensions: str) -> int: ...

    @classmethod
    def _enum_static_initializer(cls, type_name: str, value: int) -> str: ...

    @classmethod
    def _opaque_bitfield_declaration(cls, member: MemberInfo, type_name: str) -> str | None: ...

    def _generate_methods(self, methods: list[MethodInfo], class_name: str) -> list[str]: ...

    def _deduplicate_rendered_methods(self, methods: list[MethodInfo]) -> list[MethodInfo]: ...

    def _partition_methods(
        self, methods: list[MethodInfo], class_name: str, primary_name: str
    ) -> tuple[list[MethodInfo], list[MethodInfo], list[MethodInfo], list[MethodInfo]]: ...

    def _render_constructors(self, methods: list[MethodInfo], class_name: str) -> list[str]: ...

    def _render_destructors(self, methods: list[MethodInfo]) -> list[str]: ...

    def _render_regular_methods(self, methods: list[MethodInfo]) -> list[str]: ...

    def _render_operators(self, methods: list[MethodInfo]) -> list[str]: ...

    def _rendered_method_name(self, method_name: str) -> str: ...

    def _format_parameters(self, method: MethodInfo) -> str: ...

    def _deduplicate_methods(self, methods: list[MethodInfo]) -> list[MethodInfo]: ...

    def _is_constructor(self, method: MethodInfo, class_name: str, primary_name: str) -> bool: ...

    def _method_prefix(self, method: MethodInfo) -> str: ...

    def _method_suffix(self, method: MethodInfo) -> str: ...

    def _is_conversion_operator(self, method_name: str) -> bool: ...

    def _order_class_definitions(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None = None,
    ) -> list[str]: ...

    def _top_level_infos(
        self, class_infos: dict[str, ClassInfo], hierarchy_order: list[str]
    ) -> dict[str, ClassInfo]: ...

    def _definition_dependencies(
        self, class_infos: dict[str, ClassInfo], typedefs: dict[str, str] | None = None
    ) -> dict[str, set[str]]: ...

    def _add_typedef_dependencies(
        self,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str],
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None: ...

    def _add_nested_aggregate_dependencies(
        self,
        class_name: str,
        class_info: ClassInfo,
        names: set[str],
        dependencies: dict[str, set[str]],
        offset_names: dict[int, str] | None = None,
    ) -> None: ...

    def external_dependency_headers(
        self,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, str]: ...

    @staticmethod
    def _required_dependency_names(
        rendered_class_names: set[str],
        dependencies: dict[str, set[str]],
        header_names: dict[str, str],
        current_headers: set[str],
    ) -> set[str]: ...

    def _required_typedef_dependency_names(
        self,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        typedefs: dict[str, str],
        header_names: dict[str, str],
        current_headers: set[str],
    ) -> set[str]: ...

    def _add_base_dependencies(
        self,
        class_name: str,
        class_info: ClassInfo,
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None: ...

    def _add_member_dependencies(
        self,
        class_name: str,
        members: list[MemberInfo],
        names: set[str],
        dependencies: dict[str, set[str]],
        offset_names: dict[int, str] | None = None,
    ) -> None: ...

    def _member_dependency_names(
        self,
        member: MemberInfo,
        class_name: str,
        names: set[str],
        offset_names: dict[int, str] | None,
    ) -> set[str]: ...

    def _stable_topological_order(
        self, dependencies: dict[str, set[str]], hierarchy_order: list[str]
    ) -> list[str]: ...

    def _nested_names(self, class_info: ClassInfo) -> set[str]: ...

    def _collect_resolved_forward_declarations(
        self, class_infos: dict[str, ClassInfo], hierarchy_order: list[str]
    ) -> set[str]: ...

    def _hierarchy_header_prefix(self, guard_name: str) -> list[str]: ...

    def _hierarchy_dependency_include_lines(
        self, dependency_headers: dict[str, str] | None
    ) -> list[str]: ...

    @staticmethod
    def _preferred_forward_declaration(
        name: str, candidates: list[str], resolved_kinds: dict[str, str]
    ) -> str: ...

    def _normalize_typedef_forward_declarations(
        self, declarations: set[str], class_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def _aggregate_kind_names(self, info: ClassInfo) -> list[tuple[str, str]]: ...

    def _deduplicate_forward_declarations(
        self, declarations: set[str], class_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def generate_single_file_hierarchy_header(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        target_class: str,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
        resolve_forward_declarations: bool = True,
        guard_suffix: str = "_HIERARCHY_H",
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
    ) -> str: ...

    def _hierarchy_typedef_block(
        self,
        typedefs: dict[str, str] | None,
        target_class: str,
        class_infos: dict[str, ClassInfo],
    ) -> list[str]: ...

    def _hierarchy_metadata(
        self,
        class_infos: dict[str, ClassInfo],
        target_class: str,
        hierarchy_order: list[str],
        include_metadata: bool,
    ) -> list[str]: ...

    def _hierarchy_forward_declarations(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        typedefs: dict[str, str] | None,
        resolve_forward_declarations: bool,
    ) -> set[str]: ...

    def _resolved_forward_declarations(
        self,
        class_infos: dict[str, ClassInfo],
        typedefs: dict[str, str],
        enabled: bool,
    ) -> set[str]: ...

    def _base_forward_declarations(
        self, class_infos: dict[str, ClassInfo], known_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def _exclude_defined_declarations(
        self, declarations: set[str], class_infos: dict[str, ClassInfo]
    ) -> set[str]: ...

    def _hierarchy_definitions(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        include_metadata: bool,
        typedefs: dict[str, str] | None = None,
    ) -> list[str]: ...

    def _unique_definition_names(
        self, class_infos: dict[str, ClassInfo], ordered_classes: list[str]
    ) -> list[str]: ...

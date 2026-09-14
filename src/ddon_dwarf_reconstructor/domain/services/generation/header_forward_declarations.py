"""Forward-declaration planning for generated C++ headers."""

from __future__ import annotations

import re
from collections.abc import Iterator

from ...models.dwarf import ClassInfo, MemberInfo, StructInfo, TemplateTypeParam, TypeReference
from ..parsing.die_type_classifier import DIETypeClassifier
from .header_type_planning import HeaderTypePlanningService
from .rendering.operations import HeaderRenderingHost
from .rendering.type_policy import TypeExpressionPolicy

_FORWARD_DECLARABLE_CACHE: dict[int, bool] = {}


class HeaderForwardDeclarationService:
    def _collect_forward_declarations(
        self: HeaderRenderingHost,
        class_info: ClassInfo,
        typedefs: dict[str, str],
        inherited_excluded_names: set[str] | None = None,
    ) -> set[str]:
        """Collect forward declarations needed by a class and its nested types."""
        enum_names, struct_names, union_names = self._aggregate_names(class_info)
        nested_names = self._nested_aggregate_names(class_info)
        own_names = {
            self._normalize_type_name(name)
            for name in (class_info.name, class_info.qualified_name)
            if name
        }
        excluded_names = (
            (inherited_excluded_names or set())
            | enum_names
            | struct_names
            | union_names
            | nested_names
            | own_names
            | set(typedefs)
        )
        primitives = self._primitive_names()
        declarations: set[str] = set()
        for type_name, type_offset, allow_textual_pointer in self._referenced_types(class_info):
            self._add_forward_declaration(
                declarations,
                type_name,
                type_offset,
                allow_textual_pointer,
                excluded_names,
                primitives,
            )
            if type_name:
                self._collect_template_expression_declarations(
                    declarations, type_name, excluded_names, typedefs
                )
        for nested_class in class_info.nested_classes:
            declarations.update(
                self._collect_forward_declarations(nested_class, typedefs, excluded_names)
            )
        return declarations

    def _collect_template_expression_declarations(
        self: HeaderRenderingHost,
        declarations: set[str],
        type_name: str,
        excluded_names: set[str],
        typedefs: dict[str, str],
    ) -> None:
        for expression in self._template_expressions(type_name):
            raw_primary = expression.split("<", 1)[0].strip()
            if raw_primary.startswith("std::"):
                continue
            clean_primary = self._unqualify_type_expression(raw_primary)
            if raw_primary in excluded_names or clean_primary in excluded_names:
                continue
            declaration = self._aggregate_forward_declaration(expression)
            if declaration is not None:
                declarations.add(declaration)
            declarations.update(
                self._template_argument_forward_declarations(expression, set(typedefs))
            )

    @classmethod
    def _nested_aggregate_names(cls, class_info: ClassInfo) -> set[str]:
        names: set[str] = set()
        for nested_class in class_info.nested_classes:
            names.add(HeaderTypePlanningService._normalize_type_name(nested_class.name))
            if nested_class.qualified_name:
                names.add(
                    HeaderTypePlanningService._normalize_type_name(nested_class.qualified_name)
                )
            names.update(cls._nested_aggregate_names(nested_class))
        return {name for name in names if name}

    @staticmethod
    def _aggregate_names(class_info: ClassInfo) -> tuple[set[str], set[str], set[str]]:
        return (
            {enum.name for enum in class_info.enums},
            {struct.name for struct in class_info.nested_structs if struct.name is not None},
            {union.name for union in class_info.unions if union.name},
        )

    @staticmethod
    def _primitive_names() -> set[str]:
        return TypeExpressionPolicy.primitive_names()

    def _referenced_types(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for member in class_info.members:
            yield member.type_name, member.type_offset, False
            yield from HeaderForwardDeclarationService._template_argument_types(member)
        yield from self._nested_struct_types(class_info.nested_structs)
        yield from self._union_types(class_info)
        yield from self._method_types(class_info)
        yield from self._template_parameter_types(class_info)

    def _template_parameter_types(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for parameter in class_info.template_parameters:
            if isinstance(parameter, TemplateTypeParam) and parameter.argument_type:
                offset = parameter.argument_offset
                if offset is None:
                    offset = self.dwarf_index.find_symbol_offset(parameter.argument_type)
                yield parameter.argument_type, offset, False
        yield from self._specialization_name_types(class_info.name)

    def _specialization_name_types(
        self: HeaderRenderingHost, class_name: str
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        if not ("<" in class_name and class_name.endswith(">")):
            return
        opening = class_name.find("<")
        arguments = HeaderTypePlanningService._split_template_arguments(
            class_name[opening + 1 : -1]
        )
        for argument in arguments:
            clean_arg = HeaderTypePlanningService._normalize_type_name(argument)
            if clean_arg and not TypeExpressionPolicy.is_builtin(clean_arg):
                offset = self.dwarf_index.find_symbol_offset(clean_arg)
                if offset is not None:
                    yield clean_arg, offset, False

    def _nested_struct_types(
        self: HeaderRenderingHost, structs: list[StructInfo]
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for struct in structs:
            yield from self._struct_member_types(struct)

    def _union_types(
        self: HeaderRenderingHost, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for union in class_info.unions:
            for member in union.members:
                yield member.type_name, member.type_offset, True
                yield from HeaderForwardDeclarationService._template_argument_types(member)
            yield from self._nested_struct_types(union.nested_structs)

    @staticmethod
    def _method_types(
        class_info: ClassInfo,
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for method in class_info.methods:
            if hasattr(method, "return_type_offset"):
                yield method.return_type, method.return_type_offset, True
            for parameter in method.parameters or []:
                if hasattr(parameter, "type_offset"):
                    yield parameter.type_name, parameter.type_offset, True

    @staticmethod
    def _struct_member_types(
        struct: StructInfo,
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for member in struct.members:
            yield member.type_name, member.type_offset, True
            yield from HeaderForwardDeclarationService._template_argument_types(member)

    @classmethod
    def _template_argument_types(
        cls, member: MemberInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for reference in member.template_arguments:
            yield from cls._template_reference_types(reference)

    @classmethod
    def _template_reference_types(
        cls, reference: TypeReference
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        yield reference.name, reference.die_offset, False
        for nested_reference in reference.template_arguments:
            yield from cls._template_reference_types(nested_reference)

    def _add_forward_declaration(
        self: HeaderRenderingHost,
        declarations: set[str],
        type_name: str | None,
        type_offset: int | None,
        allow_textual_pointer: bool,
        excluded_names: set[str],
        primitives: set[str],
    ) -> None:
        if not self._should_forward_declare(
            type_name, type_offset, allow_textual_pointer, excluded_names, primitives
        ):
            return
        assert type_name is not None
        clean_name = self._normalize_type_name(type_name)
        declaration = self._forward_declaration_for_type(clean_name, type_offset)
        if declaration is not None:
            declarations.add(declaration)

    def _forward_declaration_for_type(
        self: HeaderRenderingHost, clean_name: str, type_offset: int | None
    ) -> str | None:
        if type_offset is None:
            return f"class {clean_name};"
        die = self.dwarf_index.get_die_by_offset(type_offset)
        if die and die.tag == "DW_TAG_typedef":
            return None
        tag_declarations = {
            "DW_TAG_enumeration_type": f"enum class {clean_name} : int;",
            "DW_TAG_structure_type": f"struct {clean_name};",
            "DW_TAG_union_type": f"union {clean_name};",
        }
        tag = getattr(die, "tag", None)
        if not isinstance(tag, str):
            return self._aggregate_forward_declaration(clean_name)
        return tag_declarations.get(tag, self._aggregate_forward_declaration(clean_name))

    def _should_forward_declare(
        self: HeaderRenderingHost,
        type_name: str | None,
        type_offset: int | None,
        allow_textual_pointer: bool,
        excluded_names: set[str],
        primitives: set[str],
    ) -> bool:
        if not type_name:
            return False
        clean_name = self._normalize_type_name(type_name)
        if "[" in clean_name or "]" in clean_name:
            return False
        if clean_name in primitives or self._is_builtin_type(clean_name):
            return False
        if clean_name in excluded_names:
            return False
        if allow_textual_pointer and self._is_textual_pointer(
            type_name, clean_name, allow_textual_pointer
        ):
            return True
        if type_offset is None:
            return self._is_textual_pointer(type_name, clean_name, allow_textual_pointer)
        return self._should_forward_declare_die(clean_name, type_offset, excluded_names)

    def _should_forward_declare_die(
        self: HeaderRenderingHost,
        clean_name: str,
        type_offset: int,
        excluded_names: set[str],
    ) -> bool:
        if clean_name in excluded_names:
            return False
        cached = _FORWARD_DECLARABLE_CACHE.get(type_offset)
        if cached is not None:
            return cached
        die = self.dwarf_index.get_die_by_offset(type_offset)
        if die and die.tag == "DW_TAG_enumeration_type":
            _FORWARD_DECLARABLE_CACHE[type_offset] = True
            return True
        if not die:
            _FORWARD_DECLARABLE_CACHE[type_offset] = False
            return False
        declarable = DIETypeClassifier.is_forward_declarable(die)
        if len(_FORWARD_DECLARABLE_CACHE) > 65536:
            _FORWARD_DECLARABLE_CACHE.clear()
        _FORWARD_DECLARABLE_CACHE[type_offset] = declarable
        return declarable

    @staticmethod
    def _is_textual_pointer(type_name: str, clean_name: str, allowed: bool) -> bool:
        return (
            allowed
            and ("*" in type_name or "&" in type_name)
            and bool(re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", clean_name))
        )

    @staticmethod
    def _aggregate_forward_declaration(clean_name: str) -> str | None:
        clean_name = HeaderTypePlanningService._normalize_type_name(clean_name)
        clean_name = HeaderTypePlanningService._unqualify_type_expression(clean_name)
        if (
            not clean_name
            or clean_name in TypeExpressionPolicy.primitive_names()
            or TypeExpressionPolicy.is_builtin(clean_name)
        ):
            return None
        template_declaration = HeaderTypePlanningService._template_forward_declaration(clean_name)
        if template_declaration is not None:
            return template_declaration
        return f"class {clean_name};"

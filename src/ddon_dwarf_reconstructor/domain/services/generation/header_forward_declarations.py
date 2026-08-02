"""Forward-declaration planning for generated C++ headers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING

from ...models.dwarf import ClassInfo, StructInfo
from ..parsing.die_type_classifier import DIETypeClassifier
from .header_type_planning import HeaderTypePlanningMixin

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext


class HeaderForwardDeclarationMixin:
    def _collect_forward_declarations(
        self: HeaderGeneratorContext,
        class_info: ClassInfo,
        typedefs: dict[str, str],
    ) -> set[str]:
        """Collect forward declarations needed by a class and its nested types."""
        enum_names, struct_names, union_names = self._aggregate_names(class_info)
        excluded_names = enum_names | struct_names | union_names | set(typedefs)
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
        for nested_class in class_info.nested_classes:
            declarations.update(self._collect_forward_declarations(nested_class, typedefs))
        return declarations

    @staticmethod
    def _aggregate_names(class_info: ClassInfo) -> tuple[set[str], set[str], set[str]]:
        return (
            {enum.name for enum in class_info.enums},
            {struct.name for struct in class_info.nested_structs if struct.name is not None},
            {union.name for union in class_info.unions if union.name},
        )

    @staticmethod
    def _primitive_names() -> set[str]:
        return {
            "int",
            "char",
            "float",
            "double",
            "void",
            "bool",
            "unknown_type",
            "unsigned",
            "signed",
            "short",
            "long",
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
            "f32",
            "f64",
        }

    def _referenced_types(
        self: HeaderGeneratorContext, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for member in class_info.members:
            yield member.type_name, member.type_offset, False
        yield from self._nested_struct_types(class_info.nested_structs)
        yield from self._union_types(class_info)
        yield from self._method_types(class_info)

    def _nested_struct_types(
        self: HeaderGeneratorContext, structs: list[StructInfo]
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for struct in structs:
            yield from self._struct_member_types(struct)

    def _union_types(
        self: HeaderGeneratorContext, class_info: ClassInfo
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for union in class_info.unions:
            for member in union.members:
                yield member.type_name, member.type_offset, True
            yield from self._nested_struct_types(union.nested_structs)

    @staticmethod
    def _method_types(
        class_info: ClassInfo,
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for method in class_info.methods:
            if hasattr(method, "return_type_offset"):
                yield method.return_type, method.return_type_offset, False
            for parameter in method.parameters or []:
                if hasattr(parameter, "type_offset"):
                    yield parameter.type_name, parameter.type_offset, False

    @staticmethod
    def _struct_member_types(
        struct: StructInfo,
    ) -> Iterator[tuple[str | None, int | None, bool]]:
        for member in struct.members:
            yield member.type_name, member.type_offset, True

    def _add_forward_declaration(
        self: HeaderGeneratorContext,
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
        die = self.dwarf_index.get_die_by_offset(type_offset) if type_offset is not None else None
        if type_offset is None:
            declarations.add(f"class {clean_name};")
        elif die and die.tag == "DW_TAG_enumeration_type":
            declarations.add(f"enum class {clean_name} : int;")
        else:
            declarations.add(self._aggregate_forward_declaration(clean_name))

    def _should_forward_declare(
        self: HeaderGeneratorContext,
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
        if type_offset is None:
            return self._is_textual_pointer(type_name, clean_name, allow_textual_pointer)
        die = self.dwarf_index.get_die_by_offset(type_offset)
        if die and die.tag == "DW_TAG_enumeration_type":
            return clean_name not in excluded_names
        if clean_name in primitives or clean_name in excluded_names or not die:
            return False
        return DIETypeClassifier.is_forward_declarable(die)

    @staticmethod
    def _is_textual_pointer(type_name: str, clean_name: str, allowed: bool) -> bool:
        return (
            allowed
            and ("*" in type_name or "&" in type_name)
            and bool(re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", clean_name))
        )

    @staticmethod
    def _aggregate_forward_declaration(clean_name: str) -> str:
        template_declaration = HeaderTypePlanningMixin._template_forward_declaration(clean_name)
        if template_declaration is not None:
            return template_declaration
        return f"class {clean_name};"

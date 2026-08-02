"""Child-DIE collection for the class-parser façade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
from ...models.dwarf import (
    ClassInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    StructInfo,
    TemplateTypeParam,
    TemplateValueParam,
    UnionInfo,
)
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)
T = TypeVar("T")


@dataclass
class ParsedClassChildren:
    """Structured result of traversing a class DIE's direct children."""

    members: list[MemberInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    enums: list[EnumInfo] = field(default_factory=list)
    nested_structs: list[StructInfo] = field(default_factory=list)
    unions: list[UnionInfo] = field(default_factory=list)
    nested_classes: list[ClassInfo] = field(default_factory=list)
    template_type_params: list[TemplateTypeParam] = field(default_factory=list)
    template_value_params: list[TemplateValueParam] = field(default_factory=list)


class ClassParserChildrenMixin:
    def _parse_class_children(
        self: ClassParserContext, cu: CompileUnit, class_die: DIE, class_name: str
    ) -> ParsedClassChildren:
        children = ParsedClassChildren()
        processed_union_offsets: set[int] = set()
        for child in class_die.iter_children():
            self._parse_class_child(cu, child, class_name, processed_union_offsets, children)
        return children

    def _parse_class_child(
        self: ClassParserContext,
        cu: CompileUnit,
        child: DIE,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None:
        if child.tag == "DW_TAG_member":
            self._append_member_child(child, class_name, processed_union_offsets, result)
        elif child.tag in {"DW_TAG_subprogram", "DW_TAG_inheritance", "DW_TAG_enumeration_type"}:
            self._parse_primary_child(child, class_name, result)
        elif child.tag in {"DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"}:
            self._parse_nested_child(cu, child, processed_union_offsets, result)
        elif child.tag in {"DW_TAG_template_type_param", "DW_TAG_template_value_param"}:
            self._parse_template_child(child, result)
        elif child.tag not in {"DW_TAG_typedef", "DW_TAG_array_type"}:
            self._log_unhandled_child(class_name, child)

    def _parse_primary_child(
        self: ClassParserContext, child: DIE, class_name: str, result: ParsedClassChildren
    ) -> None:
        if child.tag == "DW_TAG_subprogram":
            self._append_if_present(result.methods, self.parse_method(child))
        elif child.tag == "DW_TAG_inheritance":
            self._append_base_class(child, result)
        else:
            self._append_if_present(result.enums, self.parse_enum(child))

    def _parse_nested_child(
        self: ClassParserContext,
        cu: CompileUnit,
        child: DIE,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None:
        if child.tag == "DW_TAG_class_type":
            result.nested_classes.append(self.parse_class_info(cu, child))
        elif child.tag == "DW_TAG_structure_type":
            self._append_if_present(result.nested_structs, self.parse_nested_structure(child))
        else:
            self._append_union_child(child, processed_union_offsets, result)

    def _parse_template_child(
        self: ClassParserContext, child: DIE, result: ParsedClassChildren
    ) -> None:
        if child.tag == "DW_TAG_template_type_param":
            self._append_if_present(
                result.template_type_params, self.parse_template_type_param(child)
            )
        else:
            self._append_if_present(
                result.template_value_params, self.parse_template_value_param(child)
            )

    def _append_member_child(
        self: ClassParserContext,
        child: DIE,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None:
        member_result = self._parse_member_or_anonymous(child, class_name, processed_union_offsets)
        if isinstance(member_result, MemberInfo):
            result.members.append(member_result)
        elif isinstance(member_result, UnionInfo):
            result.unions.append(member_result)

    def _append_union_child(
        self: ClassParserContext,
        child: DIE,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None:
        if child.offset in processed_union_offsets:
            return
        self._append_if_present(result.unions, self.parse_union(child))

    def _append_base_class(
        self: ClassParserContext, child: DIE, result: ParsedClassChildren
    ) -> None:
        base_type = self.type_resolver.resolve_type_name(child)
        if base_type != "unknown_type":
            result.base_classes.append(base_type)

    @staticmethod
    def _append_if_present(items: list[T], item: T | None) -> None:
        if item is not None:
            items.append(item)

    @staticmethod
    def _log_unhandled_child(class_name: str, child: DIE) -> None:
        child_name = child.attributes.get("DW_AT_name")
        child_name_str = child_name.value.decode("utf-8") if child_name else "unnamed"
        logger.warning(
            "Unhandled DWARF tag in class %s: %s (name: %s) at offset 0x%x",
            class_name,
            child.tag,
            child_name_str,
            child.offset,
        )

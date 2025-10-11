#!/usr/bin/env python3

"""Class information model for DWARF parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .member_info import MemberInfo
from .method_info import MethodInfo

if TYPE_CHECKING:
    from .enum_info import EnumInfo
    from .struct_info import StructInfo
    from .template_param_info import TemplateTypeParam, TemplateValueParam
    from .union_info import UnionInfo


@dataclass
class ClassInfo:
    """Information about a class or struct."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    methods: list[MethodInfo]
    base_classes: list[str]
    enums: list[EnumInfo]
    nested_structs: list[StructInfo]
    unions: list[UnionInfo]
    alignment: int | None = None
    declaration_file: str | None = None
    declaration_line: int | None = None
    die_offset: int | None = None
    packing_info: dict[str, int] | None = None  # packing, padding, alignment hints
    template_type_params: list[TemplateTypeParam] = field(default_factory=list)
    """Template type parameters (typename T, class U, etc.)"""
    template_value_params: list[TemplateValueParam] = field(default_factory=list)
    """Template value parameters (int N, size_t Size, etc.)"""

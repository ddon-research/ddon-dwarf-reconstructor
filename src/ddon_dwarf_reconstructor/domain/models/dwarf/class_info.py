#!/usr/bin/env python3

"""Class information model for DWARF parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .member_info import MemberInfo
from .method_info import MethodInfo
from .template_rendering import TemplateRendering
from .type_reference import TypeReference
from .type_scope import TypeScope

if TYPE_CHECKING:
    from .enum_info import EnumInfo
    from .struct_info import StructInfo
    from .template_param_info import TemplateParameter
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
    cu_offset: int | None = None  # Compilation unit offset for file mapping
    packing_info: dict[str, int] | None = None  # packing, padding, alignment hints
    template_parameters: list[TemplateParameter] = field(default_factory=list)
    """Instantiated parameters in original child-DIE order."""
    template_rendering: TemplateRendering | None = None
    kind: str = "class"
    qualified_name: str | None = None
    is_declaration: bool = False
    diagnostics: list[str] = field(default_factory=list)
    nested_classes: list[ClassInfo] = field(default_factory=list)
    containing_type: str | None = None
    base_class_offsets: list[int] = field(default_factory=list)
    scope: TypeScope | None = None
    declared_aliases: list[TypeReference] = field(default_factory=list)
    source_aliases: tuple[TypeReference, ...] = ()
    """External aliases used to discover this aggregate; each retains its own scope."""
    defining_alias: TypeReference | None = None
    """Typedef naming an anonymous definition; never an invented aggregate tag."""

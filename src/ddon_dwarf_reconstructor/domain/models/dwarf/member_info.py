#!/usr/bin/env python3

"""Member information model for DWARF parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .type_reference import TypeReference

if TYPE_CHECKING:
    from .struct_info import StructInfo


@dataclass
class MemberInfo:
    """Information about a class member."""

    name: str
    type_name: str
    type_offset: int | None = None  # DIE offset of terminal type (for resolution)
    offset: int | None = None
    is_static: bool = False
    is_const: bool = False
    const_value: int | None = None
    access: str = "public"
    is_volatile: bool = False
    bit_size: int | None = None
    bit_offset: int | None = None
    declared_type_offset: int | None = None  # Immediate typedef DIE offset, when present
    inline_struct: StructInfo | None = None  # Anonymous class/struct used as a member type
    opaque_storage_size: int | None = None  # Size used for an unrepresentable by-value type
    template_arguments: tuple[TypeReference, ...] = ()

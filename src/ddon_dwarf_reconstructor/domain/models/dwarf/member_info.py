#!/usr/bin/env python3

"""Member information model for DWARF parsing."""

from dataclasses import dataclass


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

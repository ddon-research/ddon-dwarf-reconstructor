#!/usr/bin/env python3

"""Union information model for DWARF parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .member_info import MemberInfo

if TYPE_CHECKING:
    from .struct_info import StructInfo


@dataclass
class UnionInfo:
    """Information about a union."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    nested_structs: list[StructInfo]
    die_offset: int | None = None




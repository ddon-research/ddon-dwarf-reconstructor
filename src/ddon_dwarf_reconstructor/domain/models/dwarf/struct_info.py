#!/usr/bin/env python3

"""Struct information model for DWARF parsing."""

from dataclasses import dataclass

from .member_info import MemberInfo
from .type_reference import TypeReference


@dataclass
class StructInfo:
    """Information about a nested structure."""

    name: str | None
    byte_size: int
    members: list[MemberInfo]
    die_offset: int | None = None
    defining_alias: TypeReference | None = None

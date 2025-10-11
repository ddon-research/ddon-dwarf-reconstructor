#!/usr/bin/env python3

"""Enum information model for DWARF parsing."""

from dataclasses import dataclass


@dataclass
class EnumeratorInfo:
    """Information about an enum value."""

    name: str
    value: int


@dataclass
class EnumInfo:
    """Information about an enumeration."""

    name: str
    byte_size: int
    enumerators: list[EnumeratorInfo]
    declaration_file: str | None = None
    declaration_line: int | None = None

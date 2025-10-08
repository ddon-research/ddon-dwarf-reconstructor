#!/usr/bin/env python3

"""Data models for DWARF parsing.

This module contains dataclass definitions for storing parsed DWARF information.
"""

from dataclasses import dataclass


@dataclass
class MemberInfo:
    """Information about a class member."""

    name: str
    type_name: str
    offset: int | None = None
    is_static: bool = False
    is_const: bool = False
    const_value: int | None = None


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_name: str
    default_value: str | None = None


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


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    return_type: str
    parameters: list[ParameterInfo] | None = None
    is_virtual: bool = False
    vtable_index: int | None = None
    is_constructor: bool = False
    is_destructor: bool = False

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = []


@dataclass
class StructInfo:
    """Information about a nested structure."""

    name: str | None
    byte_size: int
    members: list[MemberInfo]
    die_offset: int | None = None


@dataclass
class UnionInfo:
    """Information about a union."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    nested_structs: list[StructInfo]
    die_offset: int | None = None


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

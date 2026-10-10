#!/usr/bin/env python3

"""Enum information model for DWARF parsing."""

from dataclasses import dataclass
from typing import Literal

from .type_reference import TypeReference
from .type_scope import TypeScope


@dataclass
class EnumeratorInfo:
    """Information about an enum value."""

    name: str
    value: int


@dataclass
class EnumInfo:
    """Information about an enumeration."""

    name: str
    byte_size: int | None
    enumerators: list[EnumeratorInfo]
    size_evidence: Literal["present", "absent", "invalid", "unavailable"] = "unavailable"
    declaration_file: str | None = None
    declaration_line: int | None = None
    defining_alias: TypeReference | None = None
    scoped: bool | None = None
    scopedness_evidence: Literal[
        "present",
        "explicit_false",
        "absent",
        "unavailable",
        "legacy_fixed",
        "legacy_nonfixed",
        "legacy_inconsistent",
    ] = "unavailable"
    enum_class_flag: bool | None = None
    producer_profile: str | None = None
    representation_type: TypeReference | None = None
    representation_offset: int | None = None
    fixed_base_evidence: bool | None = None
    cu_offset: int | None = None
    die_offset: int | None = None
    scope: TypeScope = TypeScope()

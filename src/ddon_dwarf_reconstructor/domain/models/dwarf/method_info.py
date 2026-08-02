#!/usr/bin/env python3

"""Method information model for DWARF parsing."""

from dataclasses import dataclass

from .parameter_info import ParameterInfo


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    return_type: str
    return_type_offset: int | None = None  # DIE offset of return type (for resolution)
    parameters: list[ParameterInfo] | None = None
    is_virtual: bool = False
    vtable_index: int | None = None
    is_constructor: bool = False
    is_destructor: bool = False
    access: str = "public"
    is_static: bool = False
    is_const: bool = False
    is_volatile: bool = False
    ref_qualifier: str | None = None
    is_noexcept: bool = False
    is_noreturn: bool = False
    is_pure_virtual: bool = False
    is_deleted: bool = False
    is_defaulted: bool = False
    is_declaration: bool = False
    declared_return_type_offset: int | None = None  # Immediate typedef DIE offset, when present

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = []

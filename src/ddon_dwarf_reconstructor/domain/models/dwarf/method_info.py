#!/usr/bin/env python3

"""Method information model for DWARF parsing."""

from dataclasses import dataclass

from .parameter_info import ParameterInfo


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


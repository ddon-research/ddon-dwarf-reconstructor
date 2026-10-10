#!/usr/bin/env python3

"""Parameter information model for DWARF parsing."""

from collections.abc import Iterable
from dataclasses import dataclass

from .type_reference import TypeReference


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_name: str
    type_offset: int | None = None  # DIE offset of parameter type (for resolution)
    default_value: str | None = None
    declared_type_offset: int | None = None  # Immediate typedef DIE offset, when present
    die_offset: int | None = None
    cu_offset: int | None = None
    is_artificial: bool = False
    type_reference: TypeReference | None = None


def real_parameters(parameters: Iterable[ParameterInfo] | None) -> tuple[ParameterInfo, ...]:
    """Return parameters that belong in a C++ declaration or definition."""
    return tuple(
        parameter
        for parameter in parameters or ()
        if not parameter.is_artificial and parameter.name != "__artificial__"
    )

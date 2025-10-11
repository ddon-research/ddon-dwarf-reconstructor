#!/usr/bin/env python3

"""Parameter information model for DWARF parsing."""

from dataclasses import dataclass


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_name: str
    type_offset: int | None = None  # DIE offset of parameter type (for resolution)
    default_value: str | None = None

#!/usr/bin/env python3

"""Parameter information model for DWARF parsing."""

from dataclasses import dataclass


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_name: str
    default_value: str | None = None

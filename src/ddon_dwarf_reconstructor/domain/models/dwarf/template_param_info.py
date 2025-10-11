#!/usr/bin/env python3

"""Template parameter information models for DWARF parsing."""

from dataclasses import dataclass
from typing import Any


@dataclass
class TemplateTypeParam:
    """Template type parameter (typename T or class T).

    Example: template <typename T>
    """

    name: str
    """Name of the type parameter (e.g., 'T', 'Key', 'Value')"""

    default_type: str | None = None
    """Default type if specified (e.g., 'int' in 'typename T = int')"""


@dataclass
class TemplateValueParam:
    """Template value parameter (non-type template parameter).

    Example: template <int N, size_t Size>
    """

    name: str
    """Name of the value parameter (e.g., 'N', 'Size')"""

    type_name: str = "int"
    """Type of the value parameter"""

    default_value: Any | None = None
    """Default value if specified (e.g., 10 in 'int N = 10')"""

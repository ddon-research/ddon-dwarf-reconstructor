#!/usr/bin/env python3

"""Template parameter information models for DWARF parsing."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TemplateTypeParam:
    """Template type parameter (typename T or class T).

    Example: template <typename T>
    """

    name: str
    """Name of the type parameter (e.g., 'T', 'Key', 'Value')"""

    argument_type: str | None = None
    """Actual substituted type, not a source default argument."""
    die_offset: int | None = None
    cu_offset: int | None = None
    argument_offset: int | None = None
    uses_default: bool | None = None


@dataclass(frozen=True, slots=True)
class TemplateValueParam:
    """Template value parameter (non-type template parameter).

    Example: template <int N, size_t Size>
    """

    name: str
    """Name of the value parameter (e.g., 'N', 'Size')"""

    type_name: str = "unknown_type"
    """Type of the value parameter"""

    argument_value: Any | None = None
    """Actual instantiated value; a default requires separate DWARF evidence."""
    die_offset: int | None = None
    cu_offset: int | None = None
    argument_offset: int | None = None
    uses_default: bool | None = None


type TemplateParameter = TemplateTypeParam | TemplateValueParam

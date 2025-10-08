"""Utility modules for DWARF generators."""

from .array_parser import parse_array_type
from .packing_analyzer import (
    analyze_member_gaps,
    calculate_packing_info,
    estimate_member_size,
    suggest_pragma_pack,
)

__all__ = [
    "parse_array_type",
    "calculate_packing_info",
    "estimate_member_size",
    "analyze_member_gaps",
    "suggest_pragma_pack",
]

"""Core module tests."""

from .test_dwarf_core import (
    test_dwarf_parser_basic_functionality,
    test_die_extractor_search_functionality,
    test_die_parsing_and_attributes
)

__all__ = [
    "test_dwarf_parser_basic_functionality",
    "test_die_extractor_search_functionality",
    "test_die_parsing_and_attributes"
]

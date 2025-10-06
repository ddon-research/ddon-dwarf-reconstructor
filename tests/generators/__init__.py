"""Generators module tests."""

from .test_header_generation import (
    test_unified_header_generator,
    test_backward_compatibility_functions,
    test_header_content_validation,
    test_generation_modes_performance
)

__all__ = [
    "test_unified_header_generator",
    "test_backward_compatibility_functions",
    "test_header_content_validation",
    "test_generation_modes_performance"
]

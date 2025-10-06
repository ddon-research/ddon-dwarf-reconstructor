"""Performance testing module for DDON DWARF Reconstructor."""

from .test_performance import (
    PerformanceMetrics,
    run_performance_tests,
    test_dwarf_parser_initialization_performance,
    test_die_extraction_performance,
    test_header_generation_performance,
    test_memory_usage_stress_test,
    test_indexing_optimization_performance,
)

__all__ = [
    "PerformanceMetrics",
    "run_performance_tests",
    "test_dwarf_parser_initialization_performance",
    "test_die_extraction_performance",
    "test_header_generation_performance",
    "test_memory_usage_stress_test",
    "test_indexing_optimization_performance",
]

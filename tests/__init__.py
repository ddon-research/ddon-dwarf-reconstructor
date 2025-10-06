"""Consolidated test suite for DDON DWARF Reconstructor.

Test Structure:
- core/: Tests for DWARF parsing and DIE extraction
- config/: Tests for configuration management
- generators/: Tests for header generation functionality
- utils/: Tests for utility functions and patches
- test_performance.py: Comprehensive performance tests
"""

from .core import (
    test_dwarf_parser_basic_functionality,
    test_die_extractor_search_functionality,
    test_die_parsing_and_attributes
)

from .config import (
    test_config_from_env,
    test_config_from_args,
    test_config_validation
)

from .generators import (
    test_unified_header_generator,
    test_backward_compatibility_functions,
    test_header_content_validation
)

from .utils import (
    test_elf_patches,
    test_quick_search,
    test_utility_functions_integration
)

__all__ = [
    # Core tests
    "test_dwarf_parser_basic_functionality",
    "test_die_extractor_search_functionality",
    "test_die_parsing_and_attributes",

    # Config tests
    "test_config_from_env",
    "test_config_from_args",
    "test_config_validation",

    # Generator tests
    "test_unified_header_generator",
    "test_backward_compatibility_functions",
    "test_header_content_validation",

    # Utility tests
    "test_elf_patches",
    "test_quick_search",
    "test_utility_functions_integration"
]

"""Consolidated test suite for DDON DWARF Reconstructor.

Test Structure:
- core/: Tests for DWARF parsing and DIE extraction
- config/: Tests for configuration management
- generators/: Tests for header generation functionality
- utils/: Tests for utility functions and patches
- performance/: Performance benchmarks and optimization tests

Run tests with pytest:
    pytest                    # Run all tests
    pytest -m unit            # Run unit tests only
    pytest -m performance     # Run performance tests only
    pytest -m "not slow"      # Skip slow tests
"""

# This file intentionally kept minimal to avoid import issues with pytest
# Individual test modules are discovered automatically by pytest
__version__ = "0.1.0"

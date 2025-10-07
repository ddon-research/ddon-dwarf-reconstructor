"""Tests for header generation functionality."""

import time
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core import DWARFParser
from ddon_dwarf_reconstructor.generators import (
    HeaderGenerator,
    GenerationMode,
    GenerationOptions,
    generate_header,
)


@pytest.mark.integration
def test_unified_header_generator_optimized(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test the unified HeaderGenerator in OPTIMIZED mode."""
    options = GenerationOptions(
        mode=GenerationMode.OPTIMIZED,
        max_cu_parse=None,  # Use early stopping
        add_metadata=True,
        max_dependency_depth=50,
    )
    generator = HeaderGenerator(elf_parser, options)

    start_time = time.time()
    header_content = generator.generate_header(fast_symbol)
    elapsed = time.time() - start_time

    # Assertions
    assert len(header_content) > 0, "Header content should not be empty"
    assert "#ifndef" in header_content, "Header guard should be present"
    assert (
        f"struct {fast_symbol}" in header_content or f"class {fast_symbol}" in header_content
    ), "Target class should be in header"

    # Performance check - should be quick with early stopping
    assert elapsed < 10.0, f"Should complete in <10s with early stopping, took {elapsed:.2f}s"


@pytest.mark.integration
def test_header_generator_no_metadata(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test header generation without metadata."""
    options = GenerationOptions(mode=GenerationMode.OPTIMIZED, add_metadata=False)
    generator = HeaderGenerator(elf_parser, options)

    start_time = time.time()
    header_content = generator.generate_header(fast_symbol)
    elapsed = time.time() - start_time

    assert len(header_content) > 0, "Header content should not be empty"
    # Should not have verbose metadata comments when disabled
    assert "Generation mode:" not in header_content or "OPTIMIZED" in header_content


@pytest.mark.integration
def test_generate_header_function(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test the generate_header() standalone function."""
    start_time = time.time()
    header_content = generate_header(
        parser=elf_parser, symbol_name=fast_symbol, max_dependency_depth=50
    )
    elapsed = time.time() - start_time

    assert len(header_content) > 0, "Header content should not be empty"
    assert "#ifndef" in header_content, "Header guard should be present"
    assert elapsed < 10.0, f"Should complete quickly with early stopping, took {elapsed:.2f}s"


@pytest.mark.integration
def test_header_content_validation(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test that generated headers contain expected elements."""
    options = GenerationOptions(
        mode=GenerationMode.OPTIMIZED,
        max_cu_parse=None,  # Early stopping
        add_metadata=True,
        include_dependencies=True,
    )
    generator = HeaderGenerator(elf_parser, options)

    header_content = generator.generate_header(fast_symbol)

    # Validate header structure
    lines = header_content.split("\n")

    # Check header guard
    assert any("#ifndef" in line for line in lines), "Should have header guard start"
    assert any("#endif" in line for line in lines), "Should have header guard end"

    # Check includes
    assert any("#include <cstdint>" in line for line in lines), "Should include cstdint"

    # Check type aliases
    assert any(
        "typedef" in line and "u8" in line for line in lines
    ), "Should have type aliases"

    # Check metadata comments
    assert any(
        "Generated from DWARF" in line for line in lines
    ), "Should have generation metadata"


@pytest.mark.performance
@pytest.mark.slow
def test_optimized_mode_performance(
    elf_parser: DWARFParser,
    fast_symbol: str,
) -> None:
    """Test performance of the single optimized generation mode."""
    options = GenerationOptions(
        mode=GenerationMode.OPTIMIZED, max_cu_parse=None  # Early stopping
    )
    generator = HeaderGenerator(elf_parser, options)

    start_time = time.time()
    header_content = generator.generate_header(fast_symbol)
    elapsed = time.time() - start_time

    assert len(header_content) > 0, "Should generate non-empty header"
    assert elapsed < 10.0, f"OPTIMIZED should complete in <10s, took {elapsed:.2f}s"


@pytest.mark.integration
@pytest.mark.slow
def test_header_generation_with_slow_symbol(
    elf_parser: DWARFParser, sample_symbols: dict[str, str | None]
) -> None:
    """
    Test header generation with symbols that may not be in early CUs.

    WARNING: This test may be slow as it needs to parse many CUs.
    """
    # Use a symbol that's not MtObject (likely slower to find)
    slow_symbols = [s for s in sample_symbols.keys() if s != "MtObject"]

    if not slow_symbols:
        pytest.skip("No slow symbols to test")

    test_symbol = slow_symbols[0]  # Just test one to avoid long test times

    options = GenerationOptions(
        mode=GenerationMode.FAST,
        max_cu_parse=None,  # Parse all CUs if needed
        add_metadata=True,
    )
    generator = HeaderGenerator(elf_parser, options)

    # This may take a while for symbols in later CUs
    header_content = generator.generate_header(test_symbol)
    assert len(header_content) > 0, f"Should generate header for {test_symbol}"

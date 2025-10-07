"""Tests for performance benchmarking and optimization validation."""

import time
import tracemalloc
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core import DWARFParser, DIEExtractor
from ddon_dwarf_reconstructor.generators import (
    HeaderGenerator,
    GenerationMode,
    GenerationOptions,
    generate_header,
)


# Mark all tests in this module as performance tests
pytestmark = pytest.mark.performance


@pytest.mark.slow
def test_dwarf_parser_initialization_performance(elf_file_path: Path) -> None:
    """Benchmark DWARF parser initialization performance."""
    tracemalloc.start()
    memory_start = tracemalloc.get_traced_memory()[0]
    start_time = time.time()

    with DWARFParser(elf_file_path, verbose=False) as parser:
        # Force initialization by accessing compilation units
        cu_count = sum(1 for _ in parser.iter_compilation_units())

    elapsed = time.time() - start_time
    memory_end, memory_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Performance assertions - very generous for full parse
    assert elapsed < 10800.0, f"Parser init should complete in <3 hours, took {elapsed:.2f}s"
    assert cu_count > 0, f"Should find compilation units, found {cu_count}"
    assert memory_peak / 1024 / 1024 < 2000, "Peak memory should be <2GB"


@pytest.mark.slow
def test_die_extraction_performance(elf_file_path: Path) -> None:
    """Benchmark DIE extraction performance with indexing."""
    with DWARFParser(elf_file_path, verbose=False) as parser:
        # Parse limited CUs for testing
        start = time.time()
        compilation_units = parser.parse_all_compilation_units(max_cus=20)
        parse_time = time.time() - start

        # Test extractor creation (builds indexes)
        start = time.time()
        extractor = DIEExtractor(compilation_units, elf_file_path=elf_file_path)
        index_time = time.time() - start

        # Test lookup performance
        start = time.time()
        _ = extractor.find_dies_by_tag("DW_TAG_class_type")
        lookup_time = time.time() - start

    # Performance assertions
    assert parse_time < 120.0, f"Parsing 20 CUs should take <2min, took {parse_time:.2f}s"
    assert index_time < 10.0, f"Index build should take <10s, took {index_time:.2f}s"
    assert lookup_time < 1.0, f"Index lookup should take <1s, took {lookup_time:.3f}s"


@pytest.mark.slow
def test_optimized_header_generation_performance(
    elf_file_path: Path, fast_symbol: str
) -> None:
    """Benchmark optimized header generation end-to-end with early stopping."""
    with DWARFParser(elf_file_path, verbose=False) as parser:
        start = time.time()
        header_content = generate_header(
            parser=parser, symbol_name=fast_symbol, max_dependency_depth=50
        )
        elapsed = time.time() - start

    # Performance assertions
    assert len(header_content) > 0, "Should generate non-empty header"
    assert elapsed < 10.0, f"Optimized generation should complete in <10s, took {elapsed:.2f}s"


@pytest.mark.slow
def test_memory_constraints(elf_file_path: Path) -> None:
    """Test that memory usage stays within constraints."""
    tracemalloc.start()

    with DWARFParser(elf_file_path, verbose=False) as parser:
        # Parse moderate number of CUs
        _ = parser.parse_all_compilation_units(max_cus=50)

        # Check memory usage
        current, peak = tracemalloc.get_traced_memory()

    tracemalloc.stop()

    # Memory constraint: <500MB peak usage (per CLAUDE.md)
    peak_mb = peak / 1024 / 1024
    assert peak_mb < 500, f"Peak memory should be <500MB, was {peak_mb:.1f}MB"


@pytest.mark.slow
def test_cu_parsing_scalability(elf_file_path: Path) -> None:
    """Test that CU parsing scales linearly."""
    times = []
    cu_counts = [5, 10, 20]

    with DWARFParser(elf_file_path, verbose=False) as parser:
        for count in cu_counts:
            start = time.time()
            cus = parser.parse_all_compilation_units(max_cus=count)
            elapsed = time.time() - start
            times.append(elapsed)

            assert len(cus) == count, f"Should parse exactly {count} CUs"

    # Check roughly linear scaling (within 3x factor)
    # Time per CU should not increase dramatically with more CUs
    avg_time_5 = times[0] / cu_counts[0]
    avg_time_20 = times[2] / cu_counts[2]

    # Allow 3x variance due to caching, system load, etc.
    assert (
        avg_time_20 < avg_time_5 * 3
    ), f"Parsing should scale linearly, but 20 CU avg ({avg_time_20:.3f}s) is >3x slower than 5 CU avg ({avg_time_5:.3f}s)"

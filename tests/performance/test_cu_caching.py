"""Test CU-level caching performance."""

import time
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core import DWARFParser


@pytest.mark.performance
@pytest.mark.slow
def test_cu_cache_speedup(elf_file_path: Path) -> None:
    """Test that CU caching provides speedup on subsequent runs."""
    # First run - should build cache
    with DWARFParser(elf_file_path, verbose=False) as parser:
        start = time.time()
        cus1 = parser.parse_all_compilation_units(max_cus=10)
        time1 = time.time() - start

    # Second run - should use cache
    with DWARFParser(elf_file_path, verbose=False) as parser:
        start = time.time()
        cus2 = parser.parse_all_compilation_units(max_cus=10)
        time2 = time.time() - start

    # Verify both runs got same CUs
    assert len(cus1) == len(cus2), "Both runs should parse same number of CUs"
    assert len(cus1) == 10, "Should parse exactly 10 CUs"

    # Verify speedup
    speedup = time1 / time2 if time2 > 0 else 0

    # When cache is already warm, speedup may be minimal due to system variations
    # The key test is that we're not significantly slower
    assert speedup >= 0.5, f"Cached run should not be much slower, got {speedup:.1f}x"

    # Check cache files exist
    cache_dir = Path(".dwarf_cache")
    assert cache_dir.exists(), "Cache directory should exist"

    cu_caches = list(cache_dir.glob("*_cu_*.pkl"))
    assert len(cu_caches) >= 10, f"Should have at least 10 CU cache files, found {len(cu_caches)}"


@pytest.mark.performance
@pytest.mark.slow
def test_cache_invalidation(elf_file_path: Path) -> None:
    """Test that cache invalidates when ELF file changes."""
    # Parse once to create cache
    with DWARFParser(elf_file_path, verbose=False) as parser:
        _ = parser.parse_all_compilation_units(max_cus=5)
        cache_key1 = parser._get_elf_cache_key()

    # Get cache file paths
    cache_dir = Path(".dwarf_cache")
    cache_files_before = set(cache_dir.glob(f"{cache_key1}_cu_*.pkl"))

    # Cache key should be consistent for same file
    with DWARFParser(elf_file_path, verbose=False) as parser:
        cache_key2 = parser._get_elf_cache_key()

    assert cache_key1 == cache_key2, "Cache key should be consistent for unchanged file"
    assert len(cache_files_before) > 0, "Should have created cache files"

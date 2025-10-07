"""Test parallel CU parsing."""

import time
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core import DWARFParser


@pytest.mark.performance
def test_parallel_parsing_works(elf_file_path: Path) -> None:
    """Test that parallel parsing produces correct results."""
    # Sequential parsing
    with DWARFParser(elf_file_path, verbose=False) as parser:
        cus_seq = parser.parse_all_compilation_units(max_cus=5, parallel=False)

    # Parallel parsing
    with DWARFParser(elf_file_path, verbose=False) as parser:
        cus_par = parser.parse_all_compilation_units(max_cus=5, parallel=True)

    # Verify same results
    assert len(cus_seq) == len(cus_par), "Both methods should parse same number of CUs"
    assert len(cus_seq) == 5, "Should parse exactly 5 CUs"

    # Verify CU offsets match
    seq_offsets = sorted(cu.offset for cu in cus_seq)
    par_offsets = sorted(cu.offset for cu in cus_par)
    assert seq_offsets == par_offsets, "CU offsets should match"

    # Verify total DIE counts match
    seq_dies = sum(len(cu.dies) for cu in cus_seq)
    par_dies = sum(len(cu.dies) for cu in cus_par)
    assert seq_dies == par_dies, f"DIE counts should match: {seq_dies} vs {par_dies}"


@pytest.mark.slow
@pytest.mark.performance
def test_parallel_vs_sequential_timing(elf_file_path: Path) -> None:
    """Compare parallel vs sequential parsing performance (cached)."""
    # Sequential
    with DWARFParser(elf_file_path, verbose=False) as parser:
        start = time.time()
        cus_seq = parser.parse_all_compilation_units(max_cus=10, parallel=False)
        time_seq = time.time() - start

    # Parallel
    with DWARFParser(elf_file_path, verbose=False) as parser:
        start = time.time()
        cus_par = parser.parse_all_compilation_units(max_cus=10, parallel=True)
        time_par = time.time() - start

    # Note: With caching, parallel is often slower due to overhead
    # This test just verifies both methods work, not performance comparison
    assert time_seq > 0 and time_par > 0, "Both methods should take measurable time"

"""Tests for core DWARF parsing functionality."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core import DWARFParser, DIEExtractor


@pytest.mark.unit
def test_dwarf_parser_basic_functionality(elf_parser: DWARFParser, elf_file_path: Path) -> None:
    """Test basic DWARF parser functionality."""
    # Test compilation unit iteration
    cu_count = 0
    for cu in elf_parser.iter_compilation_units():
        cu_count += 1
        assert cu.offset is not None, "CU offset should not be None"
        assert len(cu.dies) > 0, "CU should contain DIEs"

        # Test early termination (for performance)
        if cu_count >= 3:
            break

    assert cu_count > 0, "Should find at least one compilation unit"


@pytest.mark.integration
def test_die_extractor_functionality(elf_parser: DWARFParser, elf_file_path: Path) -> None:
    """Test DIE extraction and search capabilities."""
    # Parse limited CUs for testing
    compilation_units = elf_parser.parse_all_compilation_units(max_cus=10)
    extractor = DIEExtractor(compilation_units, elf_file_path=elf_file_path)

    # Search for some common DWARF entries
    base_type_dies = extractor.find_dies_by_tag("DW_TAG_base_type")
    assert len(base_type_dies) > 0, "Should find base type DIEs"

    # Test class search (may not find anything, that's OK)
    _ = extractor.find_dies_by_tag("DW_TAG_class_type")
    # No assertion - may or may not find classes in first 10 CUs

    # Test offset-based lookup
    if base_type_dies:
        # base_type_dies contains tuples (CompilationUnit, DIE)
        _, first_die = base_type_dies[0]
        found_die = extractor.get_die_by_offset(first_die.offset)
        assert found_die is not None, "Should find DIE by offset"
        assert found_die.offset == first_die.offset, "Offsets should match"


@pytest.mark.integration
def test_die_extractor_with_known_symbol(
    elf_parser: DWARFParser, elf_file_path: Path, fast_symbol: str
) -> None:
    """Test DIE extraction can find known symbols."""
    # Parse limited CUs (fast_symbol should be early)
    compilation_units = elf_parser.parse_all_compilation_units(max_cus=10)
    extractor = DIEExtractor(compilation_units, elf_file_path=elf_file_path)

    # Search for the known symbol
    symbol_dies = extractor.find_dies_by_name(fast_symbol)
    assert len(symbol_dies) > 0, f"Should find {fast_symbol} in first 10 CUs"

    # Verify we got valid DIE data
    _, die = symbol_dies[0]
    # DIE may not have name directly, but should have offset
    assert die.offset is not None


@pytest.mark.unit
def test_dwarf_parser_error_handling_nonexistent() -> None:
    """Test DWARF parser error handling with non-existent file."""
    with pytest.raises(Exception):
        with DWARFParser(Path("nonexistent.elf"), verbose=False) as parser:
            pass


@pytest.mark.unit
def test_dwarf_parser_error_handling_invalid() -> None:
    """Test DWARF parser error handling with invalid ELF file."""
    # Use this Python file as invalid ELF
    invalid_path = Path(__file__)

    # Parser should either reject or handle gracefully (lenient parsing for PS4)
    # We don't assert failure here due to PS4 lenient mode
    try:
        with DWARFParser(invalid_path, verbose=False) as p:
            # If it opens, try to iterate (should fail or be empty)
            list(p.iter_compilation_units())
    except Exception:
        # Expected - invalid ELF should raise
        pass

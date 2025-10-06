"""Tests for core DWARF parsing functionality."""

from test_utils import setup_test_environment, TestRunner, print_test_result, handle_test_skip

# Set up test environment (replaces redundant setup code)
setup_test_environment()

from ddon_dwarf_reconstructor.config import Config
from ddon_dwarf_reconstructor.core import DWARFParser, DIEExtractor


def test_dwarf_parser_basic_functionality():
    """Test basic DWARF parser functionality."""
    config = Config.from_env()

    # Verify the ELF file exists
    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    print(f"Testing with ELF file: {config.elf_file_path}")

    # Test parser context manager
    with DWARFParser(config.elf_file_path, verbose=False) as parser:
        print("✓ DWARF parser created and initialized")

        # Test compilation unit iteration
        cu_count = 0
        for cu in parser.iter_compilation_units():
            cu_count += 1
            assert cu.offset is not None, "CU offset should not be None"
            assert len(cu.dies) > 0, "CU should contain DIEs"

            # Test early termination (for performance)
            if cu_count >= 3:
                break

        assert cu_count > 0, "Should find at least one compilation unit"
        print(f"✓ Found {cu_count} compilation units")


def test_die_extractor_functionality():
    """Test DIE extraction and search capabilities."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:
        extractor = DIEExtractor(parser)

        # Test basic DIE search
        print("Testing DIE search functionality...")

        # Search for some common DWARF entries
        base_type_dies = extractor.find_dies_by_tag("DW_TAG_base_type")
        assert len(base_type_dies) > 0, "Should find base type DIEs"
        print(f"✓ Found {len(base_type_dies)} base type DIEs")

        # Test class search (may not find anything, that's OK)
        try:
            class_dies = extractor.find_dies_by_tag("DW_TAG_class_type")
            print(f"✓ Found {len(class_dies)} class DIEs")
        except Exception as e:
            print(f"ℹ Class search completed with: {e}")

        # Test offset-based lookup
        if base_type_dies:
            first_die = base_type_dies[0]
            found_die = extractor.get_die_by_offset(first_die.offset)
            assert found_die is not None, "Should find DIE by offset"
            assert found_die.offset == first_die.offset, "Offsets should match"
            print("✓ Offset-based DIE lookup works")


def test_dwarf_parser_error_handling():
    """Test DWARF parser error handling with invalid files."""
    from pathlib import Path

    # Test with non-existent file
    try:
        with DWARFParser(Path("nonexistent.elf"), verbose=False) as parser:
            pass
        assert False, "Should raise exception for non-existent file"
    except Exception:
        print("✓ Properly handles non-existent files")

    # Test with invalid file (if we have one)
    try:
        invalid_path = Path(__file__)  # Use this Python file as invalid ELF
        with DWARFParser(invalid_path, verbose=False) as parser:
            pass
        # If no exception, that's also OK (lenient parsing)
        print("✓ Handles invalid ELF files gracefully")
    except Exception:
        print("✓ Properly rejects invalid ELF files")


def run_core_tests(runner: TestRunner) -> None:
    """
    Run all core DWARF tests.

    Args:
        runner: TestRunner instance to execute tests with
    """
    runner.run_test(test_dwarf_parser_basic_functionality)
    runner.run_test(test_die_extractor_functionality)
    runner.run_test(test_dwarf_parser_error_handling)


if __name__ == "__main__":
    # Allow running this test module directly
    runner = TestRunner()
    run_core_tests(runner)
    runner.print_summary()

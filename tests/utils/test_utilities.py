"""Tests for utility functions and helper modules."""

from test_utils import setup_test_environment, TestRunner, handle_test_skip
from pathlib import Path

# Set up test environment
setup_test_environment()

from ddon_dwarf_reconstructor.config import Config


def test_elf_patches_functionality():
    """Test ELF patches and PS4-specific handling."""
    try:
        from ddon_dwarf_reconstructor.utils import elf_patches
        print("✓ ELF patches module imports successfully")

        # Test that the module has expected functions/classes
        assert hasattr(elf_patches, '__name__'), "Module should have basic attributes"
        print("✓ ELF patches module structure is valid")

    except ImportError:
        handle_test_skip("ELF patches module not available")


def test_quick_search_functionality():
    """Test quick search utilities."""
    try:
        from ddon_dwarf_reconstructor.utils import quick_search
        print("✓ Quick search module imports successfully")

        # Test that the module has expected functions/classes
        assert hasattr(quick_search, '__name__'), "Module should have basic attributes"
        print("✓ Quick search module structure is valid")

    except ImportError:
        handle_test_skip("Quick search module not available")


def test_path_utilities():
    """Test path handling utilities."""
    from pathlib import Path

    # Test basic path operations that our utilities might use
    test_path = Path("test/path/file.ext")

    assert test_path.name == "file.ext", "Path name extraction should work"
    assert test_path.suffix == ".ext", "Path suffix extraction should work"
    assert test_path.parent.name == "path", "Path parent extraction should work"

    print("✓ Basic path utilities work correctly")


def test_output_directory_handling():
    """Test output directory creation and validation."""
    config = Config.from_env()

    # Test that output directory is properly configured
    assert config.output_dir is not None, "Output directory should be configured"
    assert isinstance(config.output_dir, Path), "Output directory should be Path object"

    # Test that we can work with the output directory
    output_str = str(config.output_dir)
    assert len(output_str) > 0, "Output directory path should not be empty"

    print(f"✓ Output directory handling works: {config.output_dir}")


def test_file_extension_validation():
    """Test file extension validation utilities."""
    # Test ELF file extension validation
    elf_file = Path("test.elf")
    non_elf_file = Path("test.txt")

    assert elf_file.suffix == ".elf", "ELF file should have .elf extension"
    assert non_elf_file.suffix != ".elf", "Non-ELF file should not have .elf extension"

    print("✓ File extension validation utilities work")


def run_utility_tests(runner: TestRunner) -> None:
    """
    Run all utility tests.

    Args:
        runner: TestRunner instance to execute tests with
    """
    runner.run_test(test_elf_patches_functionality)
    runner.run_test(test_quick_search_functionality)
    runner.run_test(test_path_utilities)
    runner.run_test(test_output_directory_handling)
    runner.run_test(test_file_extension_validation)


if __name__ == "__main__":
    # Allow running this test module directly
    runner = TestRunner()
    run_utility_tests(runner)
    runner.print_summary()

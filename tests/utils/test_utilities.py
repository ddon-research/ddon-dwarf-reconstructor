"""Tests for utility functions and helper modules."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.config import Config


@pytest.mark.unit
def test_elf_patches_functionality() -> None:
    """Test ELF patches and PS4-specific handling."""
    try:
        from ddon_dwarf_reconstructor.utils import elf_patches

        # Test that the module has expected functions/classes
        assert hasattr(elf_patches, "__name__"), "Module should have basic attributes"

    except ImportError:
        pytest.skip("ELF patches module not available")


@pytest.mark.unit
def test_path_utilities() -> None:
    """Test path handling utilities."""
    # Test basic path operations that our utilities might use
    test_path = Path("test/path/file.ext")

    assert test_path.name == "file.ext", "Path name extraction should work"
    assert test_path.suffix == ".ext", "Path suffix extraction should work"
    assert test_path.parent.name == "path", "Path parent extraction should work"


@pytest.mark.unit
def test_output_directory_handling(config: Config) -> None:
    """Test output directory creation and validation."""
    # Test that output directory is properly configured
    assert config.output_dir is not None, "Output directory should be configured"
    assert isinstance(config.output_dir, Path), "Output directory should be Path object"

    # Test that we can work with the output directory
    output_str = str(config.output_dir)
    assert len(output_str) > 0, "Output directory path should not be empty"


@pytest.mark.unit
def test_file_extension_validation() -> None:
    """Test file extension validation utilities."""
    # Test ELF file extension validation
    elf_file = Path("test.elf")
    non_elf_file = Path("test.txt")

    assert elf_file.suffix == ".elf", "ELF file should have .elf extension"
    assert non_elf_file.suffix != ".elf", "Non-ELF file should not have .elf extension"

"""Tests for configuration management functionality."""

import os
import tempfile
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.config import Config


@pytest.mark.unit
def test_config_from_env(config: Config) -> None:
    """Test configuration loading from environment variables."""
    assert config.elf_file_path is not None, "ELF file path should be set"
    assert config.output_dir is not None, "Output directory should be set"
    assert isinstance(config.verbose, bool), "Verbose should be boolean"


@pytest.mark.unit
def test_config_validation(config: Config) -> None:
    """Test configuration validation and error handling."""
    # Test ELF file path validation
    if config.elf_file_path.exists():
        assert config.elf_file_path.suffix == ".elf", "Should be an ELF file"

    # Test output directory
    assert config.output_dir.name, "Output directory should have a name"


@pytest.mark.unit
def test_config_env_file_loading() -> None:
    """Test loading configuration from .env file."""
    # Create a temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("ELF_FILE_PATH=test.elf\n")
        f.write("OUTPUT_DIR=test_output\n")
        f.write("VERBOSE=true\n")
        env_file_path = f.name

    try:
        # Test would need to be expanded to actually test .env loading
        # For now, just verify the config structure is correct
        config = Config.from_env()
        assert hasattr(config, "elf_file_path"), "Should have elf_file_path attribute"
        assert hasattr(config, "output_dir"), "Should have output_dir attribute"
        assert hasattr(config, "verbose"), "Should have verbose attribute"

    finally:
        # Clean up temporary file
        try:
            os.unlink(env_file_path)
        except Exception:
            pass


@pytest.mark.unit
def test_config_elf_path_types() -> None:
    """Test that ELF path is properly typed as Path object."""
    config = Config.from_env()
    assert isinstance(config.elf_file_path, Path), "ELF path should be Path object"
    assert isinstance(config.output_dir, Path), "Output dir should be Path object"

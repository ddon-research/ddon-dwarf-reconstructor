"""Tests for configuration management functionality."""

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
def test_config_env_file_loading(monkeypatch) -> None:
    """Test loading configuration from environment variables (mocked)."""
    # Mock environment variables instead of creating files
    monkeypatch.setenv("ELF_FILE_PATH", "test.elf")
    monkeypatch.setenv("OUTPUT_DIR", "test_output")
    monkeypatch.setenv("VERBOSE", "true")
    
    config = Config.from_env()
    
    # Verify configuration attributes are properly loaded
    assert hasattr(config, "elf_file_path"), "Should have elf_file_path attribute"
    assert hasattr(config, "output_dir"), "Should have output_dir attribute"  
    assert hasattr(config, "verbose"), "Should have verbose attribute"
    
    # Verify the actual values (if accessible)
    assert str(config.elf_file_path).endswith("test.elf"), "Should use env ELF path"
    assert str(config.output_dir).endswith("test_output"), "Should use env output dir"


@pytest.mark.unit
def test_config_elf_path_types() -> None:
    """Test that ELF path is properly typed as Path object."""
    config = Config.from_env()
    assert isinstance(config.elf_file_path, Path), "ELF path should be Path object"
    assert isinstance(config.output_dir, Path), "Output dir should be Path object"

"""Tests for configuration management functionality."""

from test_utils import setup_test_environment, TestRunner, handle_test_skip
from pathlib import Path
import os
import tempfile

# Set up test environment
setup_test_environment()

from ddon_dwarf_reconstructor.config import Config


def test_config_from_env():
    """Test configuration loading from environment variables."""
    # Test default configuration
    config = Config.from_env()

    assert config.elf_file_path is not None, "ELF file path should be set"
    assert config.output_dir is not None, "Output directory should be set"
    assert isinstance(config.verbose, bool), "Verbose should be boolean"

    print("✓ Configuration loads from environment")
    print(f"  ELF file: {config.elf_file_path}")
    print(f"  Output dir: {config.output_dir}")
    print(f"  Verbose: {config.verbose}")


def test_config_validation():
    """Test configuration validation and error handling."""
    config = Config.from_env()

    # Test ELF file path validation
    if config.elf_file_path.exists():
        assert config.elf_file_path.suffix == '.elf', "Should be an ELF file"
        print("✓ ELF file validation works")
    else:
        print(f"ℹ ELF file not found at {config.elf_file_path} (expected for testing)")

    # Test output directory
    assert config.output_dir.name, "Output directory should have a name"
    print("✓ Output directory validation works")


def test_config_env_file_loading():
    """Test loading configuration from .env file."""
    # Create a temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("ELF_FILE_PATH=test.elf\n")
        f.write("OUTPUT_DIR=test_output\n")
        f.write("VERBOSE=true\n")
        env_file_path = f.name

    try:
        # Test would need to be expanded to actually test .env loading
        # For now, just verify the config structure is correct
        config = Config.from_env()
        assert hasattr(config, 'elf_file_path'), "Should have elf_file_path attribute"
        assert hasattr(config, 'output_dir'), "Should have output_dir attribute"
        assert hasattr(config, 'verbose'), "Should have verbose attribute"
        print("✓ Configuration structure is valid")

    finally:
        # Clean up temporary file
        os.unlink(env_file_path)


def test_config_path_types():
    """Test that configuration paths are proper Path objects."""
    config = Config.from_env()

    assert isinstance(config.elf_file_path, Path), "ELF file path should be Path object"
    assert isinstance(config.output_dir, Path), "Output dir should be Path object"

    print("✓ Configuration uses proper Path objects")


def run_config_tests(runner: TestRunner) -> None:
    """
    Run all configuration tests.

    Args:
        runner: TestRunner instance to execute tests with
    """
    runner.run_test(test_config_from_env)
    runner.run_test(test_config_validation)
    runner.run_test(test_config_env_file_loading)
    runner.run_test(test_config_path_types)


if __name__ == "__main__":
    # Allow running this test module directly
    runner = TestRunner()
    run_config_tests(runner)
    runner.print_summary()

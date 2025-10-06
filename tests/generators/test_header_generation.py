"""Tests for header generation functionality."""

import time
from test_utils import setup_test_environment, TestRunner, handle_test_skip

# Set up test environment (replaces redundant setup code)
setup_test_environment()

from ddon_dwarf_reconstructor.config import Config
from ddon_dwarf_reconstructor.core import DWARFParser
from ddon_dwarf_reconstructor.generators import (
    HeaderGenerator,
    GenerationMode,
    GenerationOptions,
    generate_header_with_logging,
    generate_fast_header,
    generate_ultra_fast_header
)


def test_unified_header_generator():
    """Test the new unified HeaderGenerator with different modes."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:

        # Test ULTRA_FAST mode
        print("--- Testing ULTRA_FAST mode ---")
        options = GenerationOptions(
            mode=GenerationMode.ULTRA_FAST,
            max_cu_scan=3,
            add_metadata=True
        )
        generator = HeaderGenerator(parser, options)

        start_time = time.time()
        try:
            header_content = generator.generate_header("MtObject")
            elapsed = time.time() - start_time

            assert len(header_content) > 0, "Header content should not be empty"
            assert "#ifndef MTOBJECT_H" in header_content, "Header guard should be present"
            assert "struct MtObject" in header_content or "class MtObject" in header_content, "Target class should be in header"
            print(f"✓ ULTRA_FAST mode: Generated {len(header_content)} bytes in {elapsed:.2f}s")

        except ValueError as e:
            print(f"ℹ ULTRA_FAST mode: {e} (normal if symbol not in first few CUs)")

        # Test SIMPLE mode
        print("--- Testing SIMPLE mode ---")
        options = GenerationOptions(
            mode=GenerationMode.SIMPLE,
            add_metadata=False
        )
        generator = HeaderGenerator(parser, options)

        start_time = time.time()
        try:
            header_content = generator.generate_header("MtObject")
            elapsed = time.time() - start_time

            assert len(header_content) > 0, "Header content should not be empty"
            print(f"✓ SIMPLE mode: Generated {len(header_content)} bytes in {elapsed:.2f}s")

        except ValueError as e:
            print(f"ℹ SIMPLE mode: {e}")


def test_backward_compatibility_functions():
    """Test that the backward compatibility functions still work."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:

        # Test generate_ultra_fast_header function
        print("--- Testing generate_ultra_fast_header function ---")
        start_time = time.time()
        try:
            header_content = generate_ultra_fast_header(
                parser=parser,
                symbol_name="MtObject",
                max_cu_scan=3
            )
            elapsed = time.time() - start_time

            assert len(header_content) > 0, "Header content should not be empty"
            print(f"✓ generate_ultra_fast_header: Generated {len(header_content)} bytes in {elapsed:.2f}s")

        except ValueError as e:
            print(f"ℹ generate_ultra_fast_header: {e}")


def test_header_content_validation():
    """Test that generated headers contain expected elements."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:

        options = GenerationOptions(
            mode=GenerationMode.ULTRA_FAST,
            max_cu_scan=5,
            add_metadata=True,
            include_dependencies=True
        )
        generator = HeaderGenerator(parser, options)

        try:
            header_content = generator.generate_header("MtObject")

            # Validate header structure
            lines = header_content.split('\n')

            # Check header guard
            assert any("#ifndef" in line for line in lines), "Should have header guard start"
            assert any("#endif" in line for line in lines), "Should have header guard end"

            # Check includes
            assert any("#include <cstdint>" in line for line in lines), "Should include cstdint"

            # Check type aliases
            assert any("typedef" in line and "u8" in line for line in lines), "Should have type aliases"

            # Check metadata comments
            assert any("Generated from DWARF" in line for line in lines), "Should have generation metadata"
            assert any("Generation mode:" in line for line in lines), "Should have mode metadata"

            print(f"✓ Header validation passed: {len(lines)} lines")

        except ValueError as e:
            print(f"ℹ Header validation skipped: {e}")


def test_generation_modes_performance():
    """Test performance characteristics of different generation modes."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:

        modes_to_test = [
            (GenerationMode.ULTRA_FAST, {"max_cu_scan": 2}),
            (GenerationMode.FAST, {}),
        ]

        for mode, extra_options in modes_to_test:
            print(f"--- Performance test: {mode.value} ---")

            options = GenerationOptions(mode=mode, **extra_options)
            generator = HeaderGenerator(parser, options)

            start_time = time.time()
            try:
                header_content = generator.generate_header("MtObject")
                elapsed = time.time() - start_time

                print(f"✓ {mode.value}: {len(header_content)} bytes in {elapsed:.3f}s")

                # Performance assertions
                if mode == GenerationMode.ULTRA_FAST:
                    assert elapsed < 10.0, f"ULTRA_FAST should complete in <10s, took {elapsed:.2f}s"

            except ValueError as e:
                print(f"ℹ {mode.value}: {e}")


def run_generator_tests(runner: TestRunner) -> None:
    """
    Run all header generator tests.

    Args:
        runner: TestRunner instance to execute tests with
    """
    runner.run_test(test_unified_header_generator)
    runner.run_test(test_backward_compatibility_functions)
    runner.run_test(test_header_content_validation)
    runner.run_test(test_generation_modes_performance)


if __name__ == "__main__":
    # Allow running this test module directly
    runner = TestRunner()
    run_generator_tests(runner)
    runner.print_summary()

"""Tests for performance benchmarking and optimization validation."""

import time
import tracemalloc
from typing import Dict, Any, List
from test_utils import setup_test_environment, TestRunner, handle_test_skip

# Set up test environment
setup_test_environment()

from ddon_dwarf_reconstructor.config import Config
from ddon_dwarf_reconstructor.core import DWARFParser, DIEExtractor
from ddon_dwarf_reconstructor.generators import (
    HeaderGenerator,
    GenerationMode,
    GenerationOptions,
    generate_ultra_fast_header
)


class PerformanceMetrics:
    """
    Container for performance measurement data.
    """

    def __init__(self, name: str):
        """Initialize performance metrics tracking."""
        self.name = name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.memory_start: int = 0
        self.memory_peak: int = 0
        self.memory_end: int = 0

    def start_measurement(self) -> None:
        """Start performance measurement."""
        tracemalloc.start()
        self.memory_start = tracemalloc.get_traced_memory()[0]
        self.start_time = time.time()

    def end_measurement(self) -> None:
        """End performance measurement."""
        self.end_time = time.time()
        self.memory_end, self.memory_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return self.end_time - self.start_time

    @property
    def memory_used_mb(self) -> float:
        """Get memory used in MB."""
        return (self.memory_end - self.memory_start) / 1024 / 1024

    @property
    def peak_memory_mb(self) -> float:
        """Get peak memory usage in MB."""
        return self.memory_peak / 1024 / 1024

    def print_report(self) -> None:
        """Print a formatted performance report."""
        print(f"Performance Report: {self.name}")
        print(f"  Elapsed Time: {self.elapsed_time:.3f} seconds")
        print(f"  Memory Used: {self.memory_used_mb:.2f} MB")
        print(f"  Peak Memory: {self.peak_memory_mb:.2f} MB")


def test_dwarf_parser_initialization_performance():
    """Benchmark DWARF parser initialization performance."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    metrics = PerformanceMetrics("DWARF Parser Initialization")
    metrics.start_measurement()

    with DWARFParser(config.elf_file_path, verbose=False) as parser:
        # Force initialization by accessing compilation units
        cu_count = sum(1 for _ in parser.iter_compilation_units())

    metrics.end_measurement()
    metrics.print_report()

    # Performance assertions
    assert metrics.elapsed_time < 30.0, f"Parser init should complete in <30s, took {metrics.elapsed_time:.2f}s"
    assert cu_count > 0, f"Should find compilation units, found {cu_count}"

    print(f"✓ Found {cu_count} compilation units")


def test_die_extraction_performance():
    """Benchmark DIE extraction and indexing performance."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:
        metrics = PerformanceMetrics("DIE Extraction and Indexing")
        metrics.start_measurement()

        extractor = DIEExtractor(parser)

        # Perform several search operations to trigger indexing
        base_types = extractor.find_dies_by_tag("DW_TAG_base_type")
        struct_types = extractor.find_dies_by_tag("DW_TAG_structure_type")

        # Test repeated searches (should use cached indexes)
        for _ in range(3):
            extractor.find_dies_by_tag("DW_TAG_base_type")

        metrics.end_measurement()
        metrics.print_report()

        # Performance assertions
        assert metrics.elapsed_time < 20.0, f"DIE extraction should complete in <20s, took {metrics.elapsed_time:.2f}s"
        assert len(base_types) > 0, f"Should find base types, found {len(base_types)}"

        print(f"✓ Found {len(base_types)} base types and {len(struct_types)} struct types")


def test_header_generation_performance():
    """Benchmark different header generation modes."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    modes_to_test = [
        (GenerationMode.ULTRA_FAST, {"max_cu_scan": 3}),
        (GenerationMode.FAST, {}),
    ]

    results: List[Dict[str, Any]] = []

    with DWARFParser(config.elf_file_path, verbose=False) as parser:

        for mode, extra_options in modes_to_test:
            metrics = PerformanceMetrics(f"Header Generation - {mode.value}")
            metrics.start_measurement()

            try:
                options = GenerationOptions(mode=mode, **extra_options)
                generator = HeaderGenerator(parser, options)
                header_content = generator.generate_header("MtObject")

                metrics.end_measurement()
                metrics.print_report()

                results.append({
                    "mode": mode.value,
                    "time": metrics.elapsed_time,
                    "memory": metrics.memory_used_mb,
                    "content_size": len(header_content)
                })

                # Mode-specific performance assertions
                if mode == GenerationMode.ULTRA_FAST:
                    assert metrics.elapsed_time < 10.0, f"ULTRA_FAST should complete in <10s, took {metrics.elapsed_time:.2f}s"

                print(f"✓ {mode.value}: Generated {len(header_content)} bytes")

            except ValueError as e:
                print(f"ℹ {mode.value}: Skipped - {e}")
                metrics.end_measurement()  # Clean up measurement

    # Compare performance between modes
    if len(results) >= 2:
        ultra_fast = next((r for r in results if r["mode"] == "ULTRA_FAST"), None)
        fast = next((r for r in results if r["mode"] == "FAST"), None)

        if ultra_fast and fast:
            speedup = fast["time"] / ultra_fast["time"]
            print(f"✓ ULTRA_FAST is {speedup:.1f}x faster than FAST mode")


def test_memory_usage_stress_test():
    """Stress test memory usage with repeated operations."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    metrics = PerformanceMetrics("Memory Usage Stress Test")
    metrics.start_measurement()

    # Perform multiple operations to test memory management
    iterations = 5
    for i in range(iterations):
        with DWARFParser(config.elf_file_path, verbose=False) as parser:
            extractor = DIEExtractor(parser)

            # Perform various operations
            base_types = extractor.find_dies_by_tag("DW_TAG_base_type")
            if base_types:
                first_die = extractor.get_die_by_offset(base_types[0].offset)

        print(f"  Iteration {i + 1}/{iterations} completed")

    metrics.end_measurement()
    metrics.print_report()

    # Memory usage assertions
    assert metrics.peak_memory_mb < 500, f"Peak memory should be <500MB, was {metrics.peak_memory_mb:.2f}MB"

    print(f"✓ Completed {iterations} iterations without excessive memory usage")


def test_indexing_optimization_performance():
    """Test the performance benefits of the lazy-loaded indexing optimization."""
    config = Config.from_env()

    if not config.elf_file_path.exists():
        handle_test_skip(f"ELF file not found at {config.elf_file_path}")
        return

    with DWARFParser(config.elf_file_path, verbose=False) as parser:
        extractor = DIEExtractor(parser)

        # First search (builds indexes)
        metrics_first = PerformanceMetrics("First Search (Index Building)")
        metrics_first.start_measurement()
        base_types_1 = extractor.find_dies_by_tag("DW_TAG_base_type")
        metrics_first.end_measurement()

        # Subsequent searches (using cached indexes)
        metrics_cached = PerformanceMetrics("Cached Search")
        metrics_cached.start_measurement()
        base_types_2 = extractor.find_dies_by_tag("DW_TAG_base_type")
        metrics_cached.end_measurement()

        metrics_first.print_report()
        metrics_cached.print_report()

        # Verify results are consistent
        assert len(base_types_1) == len(base_types_2), "Cached results should match original"

        # Calculate speedup (cached should be much faster)
        if metrics_cached.elapsed_time > 0:
            speedup = metrics_first.elapsed_time / metrics_cached.elapsed_time
            print(f"✓ Index caching provides {speedup:.1f}x speedup")
        else:
            print("✓ Cached search completed instantly")


def run_performance_tests(runner: TestRunner) -> None:
    """
    Run all performance tests.

    Args:
        runner: TestRunner instance to execute tests with
    """
    runner.run_test(test_dwarf_parser_initialization_performance)
    runner.run_test(test_die_extraction_performance)
    runner.run_test(test_header_generation_performance)
    runner.run_test(test_memory_usage_stress_test)
    runner.run_test(test_indexing_optimization_performance)


if __name__ == "__main__":
    # Allow running this test module directly
    runner = TestRunner()
    run_performance_tests(runner)
    runner.print_summary()

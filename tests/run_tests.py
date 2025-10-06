#!/usr/bin/env python3
"""
Unified test runner for the DDON DWARF Reconstructor project.

This script provides both simple and comprehensive test execution capabilities,
combining the functionality of the previous simple_test_runner and run_tests
into a single, flexible test runner.
"""

import sys
import argparse
import importlib
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from test_utils import setup_test_environment, TestRunner, print_test_header

# Set up test environment
setup_test_environment()


class UnifiedTestRunner:
    """
    Unified test runner with both simple and advanced capabilities.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the unified test runner.

        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.test_modules: List[Tuple[str, str, str]] = [
            ("config", "test_config", "Configuration and environment tests"),
            ("core", "test_dwarf_core", "Core DWARF parsing functionality tests"),
            ("generators", "test_header_generation", "Header generation tests"),
            ("utils", "test_utilities", "Utility function tests"),
            ("performance", "test_performance", "Performance benchmarks and optimization tests"),
        ]

    def discover_test_functions(self, module_path: str, module_name: str) -> List[Callable]:
        """
        Discover test functions in a given module.

        Args:
            module_path: Path to the module (e.g., "core")
            module_name: Name of the module (e.g., "test_dwarf_core")

        Returns:
            List of test functions found in the module
        """
        try:
            full_module_name = f"{module_path}.{module_name}"
            module = importlib.import_module(full_module_name)

            # Find all functions that start with 'test_'
            test_functions = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (callable(attr) and
                    attr_name.startswith('test_') and
                    not attr_name.startswith('test_utils')):
                    test_functions.append(attr)

            return test_functions

        except ImportError as e:
            if self.verbose:
                print(f"Could not import {full_module_name}: {e}")
            return []

    def run_module_tests(self, module_path: str, module_name: str, description: str) -> TestRunner:
        """
        Run all tests in a specific module.

        Args:
            module_path: Path to the module
            module_name: Name of the module
            description: Description of the module

        Returns:
            TestRunner with results from this module
        """
        runner = TestRunner()

        print(f"\n{'=' * 60}")
        print(f"  {description}")
        print(f"  Module: {module_path}.{module_name}")
        print(f"{'=' * 60}")

        # Try to use the module's run_*_tests function if available
        try:
            full_module_name = f"{module_path}.{module_name}"
            module = importlib.import_module(full_module_name)

            # Look for the standard run_*_tests function
            run_function_name = f"run_{module_path}_tests"
            if hasattr(module, run_function_name):
                run_function = getattr(module, run_function_name)
                run_function(runner)
                return runner

        except ImportError as e:
            if self.verbose:
                print(f"Could not import module {full_module_name}: {e}")

        # Fallback to individual test function discovery
        test_functions = self.discover_test_functions(module_path, module_name)

        if not test_functions:
            print(f"⚠ No test functions found in {module_path}.{module_name}")
            runner.tests_skipped += 1
            return runner

        # Run each test function
        for test_func in test_functions:
            runner.run_test(test_func)

        return runner

    def run_all_tests(self) -> int:
        """
        Run all tests in the test suite.

        Returns:
            int: Exit code (0 for success, 1 for failures)
        """
        overall_runner = TestRunner()

        print_test_header("DDON DWARF Reconstructor - Unified Test Suite")

        for module_path, module_name, description in self.test_modules:
            module_runner = self.run_module_tests(module_path, module_name, description)

            # Aggregate results
            overall_runner.tests_run += module_runner.tests_run
            overall_runner.tests_passed += module_runner.tests_passed
            overall_runner.tests_failed += module_runner.tests_failed
            overall_runner.tests_skipped += module_runner.tests_skipped
            overall_runner.failed_tests.extend(module_runner.failed_tests)

        # Print overall summary
        print(f"\n{'=' * 60}")
        print("  OVERALL TEST RESULTS")
        print(f"{'=' * 60}")
        overall_runner.print_summary()

        return overall_runner.get_exit_code()

    def run_specific_module(self, module_filter: str) -> int:
        """
        Run tests for a specific module only.

        Args:
            module_filter: Module name to filter by

        Returns:
            int: Exit code (0 for success, 1 for failures)
        """
        matching_modules = [
            (path, name, desc) for path, name, desc in self.test_modules
            if module_filter.lower() in path.lower() or module_filter.lower() in name.lower()
        ]

        if not matching_modules:
            print(f"No modules found matching filter: {module_filter}")
            return 1

        overall_runner = TestRunner()

        for module_path, module_name, description in matching_modules:
            module_runner = self.run_module_tests(module_path, module_name, description)

            # Aggregate results
            overall_runner.tests_run += module_runner.tests_run
            overall_runner.tests_passed += module_runner.tests_passed
            overall_runner.tests_failed += module_runner.tests_failed
            overall_runner.tests_skipped += module_runner.tests_skipped
            overall_runner.failed_tests.extend(module_runner.failed_tests)

        overall_runner.print_summary()
        return overall_runner.get_exit_code()

    def run_simple_tests(self) -> int:
        """
        Run tests in simple mode (equivalent to the old simple_test_runner).

        Returns:
            int: Exit code (0 for success, 1 for failures)
        """
        runner = TestRunner()

        print_test_header("DDON DWARF Reconstructor Test Suite (Simple Mode)")
        print("Running basic functionality tests...")

        # Run essential test modules only
        essential_modules = [
            ("config", "test_config", "Configuration Tests"),
            ("core", "test_dwarf_core", "Core DWARF Tests"),
            ("generators", "test_header_generation", "Header Generation Tests"),
        ]

        for module_path, module_name, description in essential_modules:
            try:
                print(f"\n--- Running {description} ---")
                module_runner = self.run_module_tests(module_path, module_name, description)

                # Aggregate results
                runner.tests_run += module_runner.tests_run
                runner.tests_passed += module_runner.tests_passed
                runner.tests_failed += module_runner.tests_failed
                runner.tests_skipped += module_runner.tests_skipped
                runner.failed_tests.extend(module_runner.failed_tests)

            except ImportError as e:
                print(f"⚠ SKIP {description}: Module import failed - {e}")
                runner.tests_skipped += 1
            except Exception as e:
                print(f"✗ ERROR {description}: {type(e).__name__}: {e}")
                runner.tests_failed += 1
                runner.failed_tests.append(description)

        # Print final summary
        runner.print_summary()
        return runner.get_exit_code()


def main() -> int:
    """
    Main entry point for the unified test runner.

    Returns:
        int: Exit code
    """
    parser = argparse.ArgumentParser(
        description="Unified test runner for the DDON DWARF Reconstructor project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests (comprehensive mode)
  python run_tests.py --simple          # Run essential tests only (simple mode)
  python run_tests.py -m core           # Run core module tests only
  python run_tests.py -m performance    # Run performance tests only
  python run_tests.py --list-modules    # List available test modules
  python run_tests.py -v                # Run with verbose output
        """
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-m", "--module",
        type=str,
        help="Run tests for a specific module only"
    )
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List available test modules"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run in simple mode (essential tests only)"
    )
    parser.add_argument(
        "--performance-only",
        action="store_true",
        help="Run performance tests only"
    )

    args = parser.parse_args()

    runner = UnifiedTestRunner(verbose=args.verbose)

    if args.list_modules:
        print("Available test modules:")
        for module_path, module_name, description in runner.test_modules:
            print(f"  {module_path}: {description}")
        return 0

    if args.performance_only:
        return runner.run_specific_module("performance")

    if args.simple:
        return runner.run_simple_tests()

    if args.module:
        return runner.run_specific_module(args.module)
    else:
        return runner.run_all_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

"""Shared test utilities to eliminate code redundancy across test files."""

import sys
import io
from pathlib import Path
from typing import NoReturn


def setup_test_environment() -> None:
    """
    Set up test environment with UTF-8 encoding and Python path.

    Configures UTF-8 output and adds src directory to sys.path for imports.
    """
    # Set UTF-8 encoding for output to handle special characters
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # Add the src directory to the path for imports
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def print_test_header(test_name: str) -> None:
    """Print formatted test header."""
    print(f"\n{'=' * 60}")
    print(f"  {test_name}")
    print(f"{'=' * 60}")


def print_test_result(test_name: str, success: bool, details: str = "") -> None:
    """Print formatted test result."""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"       {details}")


def handle_test_skip(reason: str) -> None:
    """Handle test skipping with proper formatting."""
    print(f"⚠ SKIP: {reason}")


class TestRunner:
    """Simple test runner for executing test functions and collecting results."""

    def __init__(self) -> None:
        """Initialize test runner."""
        self.tests_run: int = 0
        self.tests_passed: int = 0
        self.tests_failed: int = 0
        self.tests_skipped: int = 0
        self.failed_tests: list[str] = []

    def run_test(self, test_func: callable, test_name: str = "") -> bool:
        """
        Run single test function and handle exceptions.

        Args:
            test_func: Test function to execute
            test_name: Optional test name (defaults to function name)

        Returns:
            True if test passed, False if failed or skipped
        """
        if not test_name:
            test_name = test_func.__name__

        print_test_header(test_name)

        try:
            self.tests_run += 1
            test_func()
            self.tests_passed += 1
            print_test_result(test_name, True)
            return True

        except AssertionError as e:
            self.tests_failed += 1
            self.failed_tests.append(test_name)
            print_test_result(test_name, False, f"Assertion failed: {e}")
            return False

        except Exception as e:
            self.tests_failed += 1
            self.failed_tests.append(test_name)
            print_test_result(test_name, False, f"Exception: {type(e).__name__}: {e}")
            return False

    def print_summary(self) -> None:
        """Print test results summary."""
        print(f"\n{'=' * 60}")
        print("  TEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total tests run: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Skipped: {self.tests_skipped}")

        if self.failed_tests:
            print(f"\nFailed tests:")
            for test in self.failed_tests:
                print(f"  - {test}")

        success_rate = (self.tests_passed / max(1, self.tests_run)) * 100
        print(f"\nSuccess rate: {success_rate:.1f}%")

    def get_exit_code(self) -> int:
        """
        Get appropriate exit code for test run.

        Returns:
            0 if all tests passed, 1 if any tests failed
        """
        return 0 if self.tests_failed == 0 else 1

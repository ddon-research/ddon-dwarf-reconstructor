#!/usr/bin/env python3

"""Progress tracking for DWARF parsing operations."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    try:
        from elftools.dwarf.compileunit import CompileUnit
    except ImportError:
        CompileUnit = Any  # type: ignore[misc, assignment]
else:
    CompileUnit = Any  # type: ignore[misc, assignment]


class ProgressTracker:
    """
    Track and report DWARF parsing progress with detailed statistics.

    Provides contextual timing, compilation unit tracking, and operation
    logging for performance analysis and debugging.
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize progress tracker.

        Args:
            logger: Logger instance for progress reporting
        """
        self.logger = logger
        self.start_time = time()
        self.cu_count = 0
        self.die_count = 0
        self.operation_stack: list[tuple[str, float]] = []

    @contextmanager
    def track_operation(self, operation_name: str) -> Iterator[None]:
        """
        Track a high-level operation with timing.

        Args:
            operation_name: Name of the operation being tracked

        Yields:
            None
        """
        start_time = time()
        self.operation_stack.append((operation_name, start_time))

        self.logger.debug(f"Starting operation: {operation_name}")

        try:
            yield
            elapsed = time() - start_time
            self.logger.debug(f"Completed operation: {operation_name} in {elapsed:.3f}s")
        except Exception as e:
            elapsed = time() - start_time
            self.logger.error(f"Failed operation: {operation_name} after {elapsed:.3f}s: {e}")
            raise
        finally:
            self.operation_stack.pop()

    @contextmanager
    def track_cu(self, cu: Any) -> Iterator[None]:
        """
        Track compilation unit processing with detailed metrics.

        Args:
            cu: Compilation unit being processed

        Yields:
            None
        """
        self.cu_count += 1
        cu_start = time()

        # Extract CU information safely
        cu_offset = getattr(cu, "cu_offset", 0)
        cu_length = getattr(cu, "cu_length", 0)

        self.logger.debug(
            f"Processing CU #{self.cu_count} at 0x{cu_offset:x} (length: {cu_length} bytes)"
        )

        initial_die_count = self.die_count

        try:
            yield

            elapsed = time() - cu_start
            dies_processed = self.die_count - initial_die_count

            self.logger.debug(
                f"CU #{self.cu_count} completed in {elapsed:.3f}s ({dies_processed} DIEs processed)"
            )

        except Exception as e:
            elapsed = time() - cu_start
            self.logger.error(f"CU #{self.cu_count} failed after {elapsed:.3f}s: {e}")
            raise

    def count_die(self) -> None:
        """Increment DIE counter for statistics."""
        self.die_count += 1

    def report_summary(self) -> None:
        """Report final processing statistics."""
        total_time = time() - self.start_time

        avg_cu_time = total_time / self.cu_count if self.cu_count > 0 else 0
        avg_die_rate = self.die_count / total_time if total_time > 0 else 0

        self.logger.info(
            f"Processing complete: {self.cu_count} CUs, {self.die_count} DIEs "
            f"in {total_time:.2f}s (avg: {avg_cu_time:.3f}s/CU, "
            f"{avg_die_rate:.1f} DIEs/s)"
        )

    def get_current_context(self) -> str:
        """
        Get current operation context for logging.

        Returns:
            String describing current operation stack
        """
        if not self.operation_stack:
            return "idle"

        operations = [op[0] for op in self.operation_stack]
        return " → ".join(operations)

    def log_memory_usage(self) -> None:
        """Log current memory usage if psutil is available."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.logger.debug(f"Memory usage: {memory_mb:.1f} MB")
        except ImportError:
            # psutil not available, skip memory logging
            pass
        except Exception as e:
            self.logger.debug(f"Could not get memory usage: {e}")

    def reset(self) -> None:
        """Reset all counters and timers."""
        self.start_time = time()
        self.cu_count = 0
        self.die_count = 0
        self.operation_stack.clear()

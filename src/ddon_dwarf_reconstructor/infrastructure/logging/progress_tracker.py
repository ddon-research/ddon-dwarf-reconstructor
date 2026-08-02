"""Progress tracking for DWARF parsing operations."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Any

from ...core.observability import log_event

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
        self.start_time = perf_counter()
        self.cu_count = 0
        self.die_count = 0
        self.operation_stack: list[tuple[str, float]] = []

    @contextmanager
    def track_operation(self, operation_name: str) -> Generator[None]:
        """
        Track a high-level operation with timing.

        Args:
            operation_name: Name of the operation being tracked

        Yields:
            None
        """
        start_time = perf_counter()
        self.operation_stack.append((operation_name, start_time))
        log_event(
            self.logger, logging.DEBUG, "progress_operation_started", operation=operation_name
        )

        try:
            yield
            elapsed_ms = (perf_counter() - start_time) * 1000
            log_event(
                self.logger,
                logging.DEBUG,
                "progress_operation_completed",
                operation=operation_name,
                duration_ms=round(elapsed_ms, 3),
            )
        except Exception as error:
            elapsed_ms = (perf_counter() - start_time) * 1000
            log_event(
                self.logger,
                logging.ERROR,
                "progress_operation_failed",
                operation=operation_name,
                duration_ms=round(elapsed_ms, 3),
                exc_info=error,
            )
            raise
        finally:
            self.operation_stack.pop()

    @contextmanager
    def track_cu(self, cu: Any) -> Generator[None]:
        """
        Track compilation unit processing with detailed metrics.

        Args:
            cu: Compilation unit being processed

        Yields:
            None
        """
        self.cu_count += 1
        cu_start = perf_counter()

        # Extract CU information safely
        cu_offset = getattr(cu, "cu_offset", 0)
        cu_length = getattr(cu, "cu_length", 0)

        log_event(
            self.logger,
            logging.DEBUG,
            "compile_unit_started",
            compile_unit_index=self.cu_count,
            cu_offset=cu_offset,
            cu_length=cu_length,
        )

        initial_die_count = self.die_count

        try:
            yield

            elapsed_ms = (perf_counter() - cu_start) * 1000
            dies_processed = self.die_count - initial_die_count
            log_event(
                self.logger,
                logging.DEBUG,
                "compile_unit_completed",
                compile_unit_index=self.cu_count,
                cu_offset=cu_offset,
                dies_processed=dies_processed,
                duration_ms=round(elapsed_ms, 3),
            )

        except Exception as error:
            elapsed_ms = (perf_counter() - cu_start) * 1000
            log_event(
                self.logger,
                logging.ERROR,
                "compile_unit_failed",
                compile_unit_index=self.cu_count,
                cu_offset=cu_offset,
                duration_ms=round(elapsed_ms, 3),
                exc_info=error,
            )
            raise

    def count_die(self) -> None:
        """Increment DIE counter for statistics."""
        self.die_count += 1

    def report_summary(self) -> None:
        """Report final processing statistics."""
        total_time = perf_counter() - self.start_time

        avg_cu_time = total_time / self.cu_count if self.cu_count > 0 else 0
        avg_die_rate = self.die_count / total_time if total_time > 0 else 0

        log_event(
            self.logger,
            logging.INFO,
            "dwarf_processing_summary",
            compile_units=self.cu_count,
            dies=self.die_count,
            duration_ms=round(total_time * 1000, 3),
            average_compile_unit_ms=round(avg_cu_time * 1000, 3),
            dies_per_second=round(avg_die_rate, 3),
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
        except ImportError:
            log_event(self.logger, logging.DEBUG, "memory_metrics_unavailable")
            return
        try:
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        except (OSError, psutil.Error) as error:
            log_event(
                self.logger,
                logging.DEBUG,
                "memory_metrics_failed",
                exc_info=error,
            )
            return
        log_event(self.logger, logging.DEBUG, "memory_usage", resident_mb=round(memory_mb, 3))

    def reset(self) -> None:
        """Reset all counters and timers."""
        self.start_time = perf_counter()
        self.cu_count = 0
        self.die_count = 0
        self.operation_stack.clear()

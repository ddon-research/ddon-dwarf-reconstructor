"""Centralized logging configuration for DDON DWARF Reconstructor."""

import logging
import sys
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, Iterator, TypeVar, cast

if TYPE_CHECKING:
    try:
        from elftools.dwarf.compileunit import CompileUnit
    except ImportError:
        CompileUnit = Any
else:
    CompileUnit = Any

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


class LoggerSetup:
    """Manages logging configuration for the application."""

    _initialized = False
    _log_file_path: Path | None = None

    @classmethod
    def initialize(cls, log_dir: Path, verbose: bool = False) -> None:
        """
        Initialize the logging system with console and file handlers.

        Args:
            log_dir: Directory to store log files
            verbose: If True, set console to DEBUG level; otherwise INFO
        """
        if cls._initialized:
            return

        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls._log_file_path = log_dir / f"ddon_reconstructor_{timestamp}.log"

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all levels

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler - level depends on verbose flag
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler - always DEBUG level
        file_handler = logging.FileHandler(cls._log_file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        cls._initialized = True

        # Log initialization message
        logger = logging.getLogger(__name__)
        logger.info(f"Logging initialized. Log file: {cls._log_file_path}")
        logger.debug(f"Verbose mode: {verbose}")

    @classmethod
    def get_log_file_path(cls) -> Path | None:
        """Get the current log file path."""
        return cls._log_file_path

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if logging has been initialized."""
        return cls._initialized


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_timing(func: F) -> F:
    """
    Decorator to log execution time of a function.

    Args:
        func: Function to decorate

    Returns:
        Wrapped function that logs timing
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = get_logger(func.__module__)
        func_name = func.__qualname__

        logger.debug(f"Starting {func_name}")
        start_time = time()

        try:
            result = func(*args, **kwargs)
            elapsed = time() - start_time
            logger.debug(f"Completed {func_name} in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time() - start_time
            logger.error(f"Failed {func_name} after {elapsed:.2f}s: {e}")
            raise

    return cast("F", wrapper)


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
        cu_offset = getattr(cu, 'cu_offset', 0)
        cu_length = getattr(cu, 'cu_length', 0)
        
        self.logger.debug(
            f"Processing CU #{self.cu_count} at 0x{cu_offset:x} "
            f"(length: {cu_length} bytes)"
        )
        
        initial_die_count = self.die_count
        
        try:
            yield
            
            elapsed = time() - cu_start
            dies_processed = self.die_count - initial_die_count
            
            self.logger.debug(
                f"CU #{self.cu_count} completed in {elapsed:.3f}s "
                f"({dies_processed} DIEs processed)"
            )
            
        except Exception as e:
            elapsed = time() - cu_start
            self.logger.error(
                f"CU #{self.cu_count} failed after {elapsed:.3f}s: {e}"
            )
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

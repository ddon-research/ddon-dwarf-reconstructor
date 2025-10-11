#!/usr/bin/env python3

"""Logger setup and configuration for the application."""

import logging
import sys
from datetime import datetime
from pathlib import Path


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

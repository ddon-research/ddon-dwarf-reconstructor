#!/usr/bin/env python3

"""Logging utility functions and decorators."""

import logging
from collections.abc import Callable
from functools import wraps
from time import time
from typing import Any, TypeVar, cast

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


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

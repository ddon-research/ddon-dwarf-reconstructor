"""Technology-neutral logging helpers used by the runtime core."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from time import time
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str) -> logging.Logger:
    """Return the standard-library logger for a module."""
    return logging.getLogger(name)


def log_timing(func: F) -> F:
    """Log debug timing for a callable without coupling it to an adapter."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = get_logger(func.__module__)
        func_name = func.__qualname__
        logger.debug("Starting %s", func_name)
        started_at = time()
        try:
            result = func(*args, **kwargs)
        except Exception as error:
            logger.error("Failed %s after %.2fs: %s", func_name, time() - started_at, error)
            raise
        logger.debug("Completed %s in %.2fs", func_name, time() - started_at)
        return result

    return cast("F", wrapper)

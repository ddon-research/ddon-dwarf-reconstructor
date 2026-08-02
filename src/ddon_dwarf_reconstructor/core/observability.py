"""Technology-neutral observability helpers used by the runtime core.

The core deliberately exposes the standard-library logging API.  The
infrastructure composition root can attach structlog processors, JSON
renderers, or an OpenTelemetry bridge without making domain code depend on
those adapters.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter
from types import TracebackType
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])
ExcInfo = (
    bool | BaseException | tuple[type[BaseException], BaseException, TracebackType | None] | None
)
_log_context: ContextVar[dict[str, object] | None] = ContextVar("ddon_log_context", default=None)


def get_logger(name: str) -> logging.Logger:
    """Return the standard-library logger for a module."""
    return logging.getLogger(name)


def current_context() -> dict[str, object]:
    """Return a copy of the structured fields bound to the current execution context."""
    return dict(_log_context.get() or {})


@contextmanager
def bind_context(**fields: object) -> Generator[None]:
    """Temporarily bind structured fields to all records in this context."""
    context = current_context()
    context.update(fields)
    token = _log_context.set(context)
    try:
        yield
    finally:
        _log_context.reset(token)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    fields: Mapping[str, object] | None = None,
    exc_info: ExcInfo = None,
    stack_info: bool = False,
    stacklevel: int = 2,
    **named_fields: object,
) -> None:
    """Emit one structured event through the standard-library logger boundary."""
    event_fields = dict(fields or {})
    event_fields.update(named_fields)
    logger.log(
        level,
        event,
        extra={"ddon_fields": event_fields},
        exc_info=exc_info,
        stack_info=stack_info,
        stacklevel=stacklevel,
    )


def log_exception(
    logger: logging.Logger, event: str, error: BaseException, **fields: object
) -> None:
    """Emit an error event with the complete chained exception traceback."""
    log_event(logger, logging.ERROR, event, fields=fields, exc_info=error, stacklevel=3)


def log_timing(func: F) -> F:
    """Log low-noise start, completion, and failure timing for a callable."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = get_logger(func.__module__)
        operation = func.__qualname__
        started_at = perf_counter()
        log_event(logger, logging.DEBUG, "operation_started", operation=operation)
        try:
            result = func(*args, **kwargs)
        except Exception as error:
            log_exception(
                logger,
                "operation_failed",
                error,
                operation=operation,
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
            )
            raise
        log_event(
            logger,
            logging.DEBUG,
            "operation_completed",
            operation=operation,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
        return result

    return cast("F", wrapper)

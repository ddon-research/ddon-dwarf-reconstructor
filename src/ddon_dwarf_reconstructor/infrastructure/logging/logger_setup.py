"""Structured logging setup for command-line execution."""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Literal, TextIO, cast

import structlog
from rich.console import Console
from structlog.dev import RichTracebackFormatter
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.stdlib import ProcessorFormatter
from structlog.types import EventDict, Processor, WrappedLogger

from ...core.observability import current_context, log_event


def _merge_bound_context(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add context fields without requiring a structlog logger in core code."""
    for key, value in current_context().items():
        event_dict.setdefault(key, value)
    return event_dict


def _merge_record_fields(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Promote fields passed by stdlib ``extra`` to the event root."""
    record = event_dict.get("_record")
    if record is None:
        return event_dict
    fields = getattr(record, "ddon_fields", {})
    if isinstance(fields, dict):
        for key, value in fields.items():
            event_dict.setdefault(key, value)
    return event_dict


def _system_timestamp(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    event_dict["timestamp"] = datetime.now().astimezone().isoformat()
    return event_dict


def _json_default(value: object) -> object:
    """Encode common diagnostic values while keeping arbitrary objects bounded."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return repr(value)


def _shared_processors() -> list[Processor]:
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _merge_bound_context,
        _merge_record_fields,
        _system_timestamp,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        CallsiteParameterAdder(
            {CallsiteParameter.FILENAME, CallsiteParameter.LINENO, CallsiteParameter.FUNC_NAME}
        ),
    ]


def _diagnostic_stream() -> TextIO:
    """Keep Click's temporary stderr from becoming a long-lived handler target."""
    stream = sys.stderr
    return cast(
        TextIO,
        sys.__stderr__ if getattr(stream, "name", None) == "<stderr>" else stream,
    )


def _console_formatter(shared: list[Processor]) -> ProcessorFormatter:
    rich_console = Console(file=_diagnostic_stream())
    color_system = cast(
        Literal["standard", "256", "truecolor", "windows", "auto"] | None,
        rich_console.color_system,
    )
    rich_traceback = RichTracebackFormatter(
        color_system=color_system,
        show_locals=False,
        max_frames=100,
        extra_lines=1,
    )
    renderer = structlog.dev.ConsoleRenderer(
        colors=color_system is not None,
        exception_formatter=rich_traceback,
    )
    return ProcessorFormatter(
        processors=[ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=shared,
    )


def _file_formatter(shared: list[Processor]) -> ProcessorFormatter:
    renderer = structlog.processors.JSONRenderer(sort_keys=True, default=_json_default)
    return ProcessorFormatter(
        processors=[
            ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            renderer,
        ],
        foreign_pre_chain=shared,
    )


class LoggerSetup:
    """Install one JSON file handler and one human-readable stderr handler."""

    _initialized = False
    _log_file_path: Path | None = None
    _configuration: tuple[Path, bool] | None = None
    _handlers: tuple[logging.Handler, logging.Handler] | None = None

    @classmethod
    def initialize(cls, log_dir: Path, verbose: bool = False) -> None:
        """Configure root logging while preserving handlers owned by callers."""
        configuration = (log_dir.resolve(), verbose)
        if cls._initialized and cls._configuration == configuration:
            return
        if cls._initialized:
            cls.shutdown()

        configuration[0].mkdir(parents=True, exist_ok=True)
        log_path = configuration[0] / f"ddon_reconstructor_{os.getpid()}_{_timestamp()}.jsonl"
        shared = _shared_processors()
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler(_diagnostic_stream())
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_handler.setFormatter(_console_formatter(shared))
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_file_formatter(shared))
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        cls._handlers = (console_handler, file_handler)
        cls._log_file_path = log_path
        cls._configuration = configuration
        cls._initialized = True
        structlog.configure(
            processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )
        log_event(
            logging.getLogger(__name__),
            logging.DEBUG,
            "logging_initialized",
            log_file=log_path,
            verbose=verbose,
            format="jsonl",
        )

    @classmethod
    def shutdown(cls) -> None:
        """Remove only handlers installed by this class, primarily for tests."""
        root_logger = logging.getLogger()
        for handler in cls._handlers or ():
            root_logger.removeHandler(handler)
            handler.close()
        cls._handlers = None
        cls._configuration = None
        cls._log_file_path = None
        cls._initialized = False
        structlog.reset_defaults()

    @classmethod
    def get_log_file_path(cls) -> Path | None:
        """Return the current JSON-lines log path."""
        return cls._log_file_path

    @classmethod
    def is_initialized(cls) -> bool:
        """Return whether this setup owns an installed logging configuration."""
        return cls._initialized


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")

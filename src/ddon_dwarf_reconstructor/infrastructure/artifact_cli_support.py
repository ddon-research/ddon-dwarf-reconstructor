"""Shared JSON/error handling for durable artifact commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import typer

from .logging import LoggerSetup, get_logger, log_exception

logger = get_logger(__name__)


def write_result(result: dict[str, object]) -> None:
    """Write one bounded artifact result to stdout."""
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


def run_operation(operation: Callable[[], None]) -> None:
    """Run an artifact operation with the repository's structured error boundary."""
    try:
        LoggerSetup.initialize(Path("logs"))
        operation()
    except Exception as error:
        log_exception(logger, "artifact_operation_failed", error, operation=operation.__name__)
        typer.echo(f"Artifact operation failed: {error}", err=True)
        raise typer.Exit(code=1) from error


__all__ = ["run_operation", "write_result"]

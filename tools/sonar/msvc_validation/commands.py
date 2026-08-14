"""Bounded command execution for compiler evidence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandExecution:
    """Result of one bounded external command."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def run_command(arguments: list[str], *, timeout_seconds: int) -> CommandExecution:
    """Run a command without turning timeout into a successful validation."""
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return CommandExecution(
            None,
            _text(error.stdout),
            _text(error.stderr),
            timed_out=True,
        )
    return CommandExecution(result.returncode, result.stdout, result.stderr)


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value

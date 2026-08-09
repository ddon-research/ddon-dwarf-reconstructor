"""Lazy loading for analytical backend modules."""

from __future__ import annotations

import importlib
from typing import Any


class AnalyticalDependencyError(RuntimeError):
    """Raised when an explicitly requested analytical backend is unavailable."""


def import_optional(module_name: str, extra: str) -> Any:
    """Import one backend module with an actionable installation diagnostic."""
    try:
        return importlib.import_module(module_name)
    except ImportError as error:
        raise AnalyticalDependencyError(
            f"Analytical backend requires installed dependency {module_name!r}; "
            f"repair the default locked environment with `uv sync --locked` (backend: {extra})"
        ) from error

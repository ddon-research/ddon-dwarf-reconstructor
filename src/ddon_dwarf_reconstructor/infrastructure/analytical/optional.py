"""Lazy optional-dependency loading for analytical projections."""

from __future__ import annotations

import importlib
from typing import Any


class AnalyticalDependencyError(RuntimeError):
    """Raised when an explicitly requested analytical backend is unavailable."""


def import_optional(module_name: str, extra: str) -> Any:
    """Import one optional module with an actionable installation diagnostic."""
    try:
        return importlib.import_module(module_name)
    except ImportError as error:
        raise AnalyticalDependencyError(
            f"Analytical backend requires optional dependency {module_name!r}; "
            f"install it with `uv sync --group {extra}`"
        ) from error

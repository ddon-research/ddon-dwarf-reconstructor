"""Typed, atomic helpers for Windows header validation evidence."""

from .catalog import HeaderCatalog, HeaderCatalogEntry, build_header_catalog
from .commands import CommandExecution, run_command
from .publication import write_json_atomic
from .reports import ValidationCounts, validation_counts

__all__ = [
    "CommandExecution",
    "HeaderCatalog",
    "HeaderCatalogEntry",
    "ValidationCounts",
    "build_header_catalog",
    "run_command",
    "validation_counts",
    "write_json_atomic",
]

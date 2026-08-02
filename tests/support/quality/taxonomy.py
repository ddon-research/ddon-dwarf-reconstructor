"""Shared pytest taxonomy policy for the root test suite."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

SCOPE_MARKERS = frozenset({"unit", "integration", "acceptance"})
PURPOSE_MARKERS = frozenset({"functional", "regression", "non_functional"})


def _has_marker(item: pytest.Item, marker: str) -> bool:
    """Return whether any marker with the given name is attached to an item."""
    return item.get_closest_marker(marker) is not None


def _attached_markers(item: pytest.Item, names: Iterable[str]) -> set[str]:
    """Return the named markers attached to an item."""
    return {name for name in names if _has_marker(item, name)}


def apply_default_functional_purpose(item: pytest.Item) -> None:
    """Make ordinary scoped tests functional while preserving explicit purposes."""
    if _attached_markers(item, SCOPE_MARKERS) and not _attached_markers(item, PURPOSE_MARKERS):
        item.add_marker(pytest.mark.functional)


def taxonomy_errors(item: pytest.Item) -> tuple[str, ...]:
    """Return actionable taxonomy violations for one collected test item."""
    scopes = _attached_markers(item, SCOPE_MARKERS)
    purposes = _attached_markers(item, PURPOSE_MARKERS)
    errors: list[str] = []
    if len(scopes) != 1:
        errors.append(f"requires exactly one scope marker ({', '.join(sorted(scopes)) or 'none'})")
    if not purposes:
        errors.append("requires a purpose marker")
    errors.extend(_qualifier_errors(item, scopes))
    return tuple(errors)


def _qualifier_errors(item: pytest.Item, scopes: set[str]) -> list[str]:
    """Validate qualifiers that impose additional scope or purpose requirements."""
    errors: list[str] = []
    if _has_marker(item, "performance") and not _has_marker(item, "non_functional"):
        errors.append("performance tests must be non_functional")
    if _has_marker(item, "quality") and not _has_marker(item, "non_functional"):
        errors.append("quality tests must be non_functional")
    if _has_marker(item, "real_asset") and not scopes.intersection({"integration", "acceptance"}):
        errors.append("real_asset tests must be integration or acceptance")
    if _has_marker(item, "packaging") and not _has_marker(item, "acceptance"):
        errors.append("packaging tests must be acceptance tests")
    return errors

"""Regression tests for the repository test taxonomy policy."""

from __future__ import annotations

import pytest

from tests.support.quality.taxonomy import taxonomy_errors

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


class _Item:
    """Small marker-bearing test item used to exercise taxonomy rules."""

    def __init__(self, *markers: str) -> None:
        self.markers = set(markers)

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name in self.markers else None


def test_scope_and_purpose_are_required() -> None:
    errors = taxonomy_errors(_Item())  # type: ignore[arg-type]

    assert "requires exactly one scope marker (none)" in errors
    assert "requires a purpose marker" in errors


def test_scope_must_be_unambiguous() -> None:
    errors = taxonomy_errors(_Item("unit", "integration", "functional"))  # type: ignore[arg-type]

    assert errors == ("requires exactly one scope marker (integration, unit)",)


def test_qualifiers_require_compatible_scope_and_purpose() -> None:
    errors = taxonomy_errors(_Item("unit", "performance", "quality"))  # type: ignore[arg-type]

    assert "performance tests must be non_functional" in errors
    assert "quality tests must be non_functional" in errors


def test_real_asset_and_packaging_rules_are_explicit() -> None:
    real_errors = taxonomy_errors(_Item("unit", "functional", "real_asset"))  # type: ignore[arg-type]
    package_errors = taxonomy_errors(_Item("integration", "functional", "packaging"))  # type: ignore[arg-type]

    assert "real_asset tests must be integration or acceptance" in real_errors
    assert "packaging tests must be acceptance tests" in package_errors

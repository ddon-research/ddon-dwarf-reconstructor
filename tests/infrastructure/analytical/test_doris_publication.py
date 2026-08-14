"""Bounded publication verification and incomplete-load evidence tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical import doris_publication
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_layout import _FAMILIES
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_publication import (
    DorisPublicationVerifier,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _connection_with_counts(*count_batches: int) -> MagicMock:
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.side_effect = [[(count,)] for count in count_batches]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection


def test_publication_verifier_waits_for_source_bound_family_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {family: 1 for family in _FAMILIES}
    connection = _connection_with_counts(
        *([0] * len(_FAMILIES)),
        *([1] * len(_FAMILIES)),
    )
    monkeypatch.setattr(doris_publication.time, "sleep", lambda _seconds: None)

    result = DorisPublicationVerifier(1.0, poll_interval_seconds=0.001).verify(
        connection,
        "dwarf",
        "records",
        "a" * 64,
        expected,
    )

    assert result.status == "observed"
    assert result.observed_counts == expected
    assert result.attempts == 2
    assert result.to_dict()["row_count_verified"] is True


def test_publication_verifier_marks_timeout_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter((0.0, 1.0))
    monkeypatch.setattr(doris_publication.time, "monotonic", lambda: next(clock))
    connection = _connection_with_counts(*([0] * len(_FAMILIES)))
    expected = {family: 1 for family in _FAMILIES}

    result = DorisPublicationVerifier(1.0).verify(
        connection,
        "dwarf",
        "records",
        "a" * 64,
        expected,
    )

    assert result.status == "partial"
    assert result.observed_counts == {family: 0 for family in _FAMILIES}
    assert result.to_dict()["row_count_verified"] is False


def test_publication_verifier_bounds_query_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter((0.0, 1.0))
    monkeypatch.setattr(doris_publication.time, "monotonic", lambda: next(clock))
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.execute.side_effect = OSError("backend unavailable" * 1000)
    connection = MagicMock()
    connection.cursor.return_value = cursor

    result = DorisPublicationVerifier(1.0).verify(
        connection,
        "dwarf",
        "records",
        "a" * 64,
        {family: 1 for family in _FAMILIES},
    )

    assert result.status == "partial"
    assert result.diagnostics
    assert all(len(item) <= 2048 for item in result.diagnostics)

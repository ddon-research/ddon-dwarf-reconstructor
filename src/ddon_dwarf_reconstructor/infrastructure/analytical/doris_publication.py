"""Bounded verification for Doris Stream Load publication."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .doris_layout import _FAMILIES, _family_table, _identifier


@dataclass(frozen=True, slots=True)
class PublicationVerification:
    """Evidence that a source-bound load is visible with complete counts."""

    status: str
    source_id: str
    expected_counts: dict[str, int]
    observed_counts: dict[str, int]
    attempts: int
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": self.source_id,
            "expected_counts": dict(self.expected_counts),
            "observed_counts": dict(self.observed_counts),
            "attempts": self.attempts,
            "diagnostics": list(self.diagnostics),
            "row_count_verified": self.status == "observed",
        }


class DorisPublicationVerifier:
    """Poll source-bound family counts until publication is proven or bounded out."""

    def __init__(self, timeout_seconds: float, poll_interval_seconds: float = 0.25) -> None:
        if timeout_seconds <= 0:
            raise ValueError("publication verification timeout must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("publication verification poll interval must be positive")
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def verify(
        self,
        connection: Any,
        database: str,
        base_table: str,
        source_id: str,
        expected_counts: dict[str, int],
    ) -> PublicationVerification:
        """Return partial evidence when the bounded publication window expires."""
        deadline = time.monotonic() + self._timeout_seconds
        attempts = 0
        diagnostics: list[str] = []
        observed: dict[str, int] = {}
        while True:
            attempts += 1
            try:
                observed = self._observed_counts(connection, database, base_table, source_id)
            except Exception as error:
                diagnostics.append(_bounded_diagnostic(error))
            if observed == expected_counts:
                return PublicationVerification(
                    "observed", source_id, expected_counts, observed, attempts, tuple(diagnostics)
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return PublicationVerification(
                    "partial", source_id, expected_counts, observed, attempts, tuple(diagnostics)
                )
            time.sleep(min(self._poll_interval_seconds, remaining))

    @staticmethod
    def _observed_counts(
        connection: Any, database: str, base_table: str, source_id: str
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        with connection.cursor() as cursor:
            for family in _FAMILIES:
                table = f"{_identifier(database)}.{_identifier(_family_table(base_table, family))}"
                cursor.execute(
                    f"SELECT COUNT(*) AS row_count FROM {table} WHERE source_id = %s",
                    (source_id,),
                )
                rows = cursor.fetchall()
                counts[family] = int(rows[0][0]) if rows else 0
        return counts


def _bounded_diagnostic(error: Exception, limit: int = 2048) -> str:
    text = f"publication verification query failed: {error}"
    suffix = "...[truncated]"
    return text if len(text) <= limit else text[: limit - len(suffix)] + suffix


__all__ = ["DorisPublicationVerifier", "PublicationVerification"]

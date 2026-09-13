"""Tests for bounded candidate statistics evidence capture."""

from __future__ import annotations

import pytest

import ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.optimization as benchmark_optimization_module

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Connection:
    def __init__(self) -> None:
        self.statements: list[str] = []


class _Cursor:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection
        self.description = (("name",),)
        self.rows: list[tuple[object, ...]] = [("value",)]

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback

    def execute(self, statement: str, params: object = ()) -> None:
        del params
        self.connection.statements.append(statement)

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


def test_candidate_evidence_capture_serializes_rows_and_failures() -> None:
    observed = benchmark_optimization_module._capture_candidate_rows(
        _Cursor(_Connection()), "SHOW TABLE STATS dwarf.records"
    )
    assert observed["status"] == "observed"
    assert observed["rows"] == [{"name": "value"}]

    class FailingCursor:
        description: tuple[tuple[str], ...] = ()

        def execute(self, _statement: str) -> None:
            raise RuntimeError("candidate stats unavailable")

        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    partial = benchmark_optimization_module._capture_candidate_rows(
        FailingCursor(), "SHOW TABLETS FROM dwarf.records"
    )
    assert partial["status"] == "partial"
    assert "unavailable" in str(partial["error"])

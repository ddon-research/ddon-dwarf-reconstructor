"""Bounded Parquet scan contracts for targeted definition lookup."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_store_access import (
    _read_bounded_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Batch:
    def __init__(self, rows: list[dict[str, int]]) -> None:
        self._rows = rows

    def to_pylist(self) -> list[dict[str, int]]:
        return list(self._rows)


class _Scanner:
    def __init__(self, batches: list[_Batch]) -> None:
        self._batches = batches
        self.consumed = 0

    def to_batches(self):
        for batch in self._batches:
            self.consumed += 1
            yield batch


class _Dataset:
    def __init__(self, batches: list[_Batch]) -> None:
        self.scanner_instance = _Scanner(batches)
        self.scanner_options: dict[str, object] | None = None

    def scanner(self, **options: object) -> _Scanner:
        self.scanner_options = options
        return self.scanner_instance


def test_unordered_bounded_scan_stops_after_the_safety_bound() -> None:
    dataset = _Dataset(
        [
            _Batch([{"unit_offset": 2}, {"unit_offset": 1}]),
            _Batch([{"unit_offset": 0}]),
        ]
    )

    rows = _read_bounded_rows(
        dataset,
        None,
        ["unit_offset"],
        limit=2,
        order_key=None,
    )

    assert rows == [{"unit_offset": 2}, {"unit_offset": 1}]
    assert dataset.scanner_instance.consumed == 1
    assert dataset.scanner_options is not None
    assert dataset.scanner_options["batch_size"] == 2


def test_ordered_bounded_scan_keeps_deterministic_top_rows_across_batches() -> None:
    dataset = _Dataset(
        [
            _Batch([{"unit_offset": 8}, {"unit_offset": 2}]),
            _Batch([{"unit_offset": 1}, {"unit_offset": 5}]),
            _Batch([{"unit_offset": 0}]),
        ]
    )

    rows = _read_bounded_rows(
        dataset,
        None,
        ["unit_offset"],
        limit=3,
        order_key=lambda row: (row["unit_offset"],),
    )

    assert rows == [{"unit_offset": 0}, {"unit_offset": 1}, {"unit_offset": 2}]
    assert dataset.scanner_instance.consumed == 3

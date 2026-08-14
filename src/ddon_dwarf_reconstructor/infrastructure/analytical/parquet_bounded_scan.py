"""Bounded Parquet scanning with deterministic fallback behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .parquet_store_helpers import is_zstd_scan_error as _is_zstd_scan_error


def read_bounded_rows(
    dataset: Any,
    expression: Any,
    selected: list[str],
    *,
    limit: int,
    order_key: Callable[[dict[str, Any]], tuple[int, ...]] | None,
) -> list[dict[str, Any]]:
    """Read a bounded working set while retaining deterministic top rows.

    PyArrow datasets do not expose a portable SQL-style ``LIMIT`` on
    ``to_table``. A scanner lets the adapter stop early for unordered reads;
    definition lookups use a bounded top-k buffer so stable record ordering is
    preserved without materializing every duplicate-name row.
    """
    try:
        return _scan_bounded_rows(
            dataset,
            expression,
            selected,
            limit=limit,
            order_key=order_key,
            use_threads=True,
        )
    except OSError as error:
        if not _is_zstd_scan_error(error):
            raise
        return _scan_bounded_rows(
            dataset,
            expression,
            selected,
            limit=limit,
            order_key=order_key,
            use_threads=False,
        )


def _scan_bounded_rows(
    dataset: Any,
    expression: Any,
    selected: list[str],
    *,
    limit: int,
    order_key: Callable[[dict[str, Any]], tuple[int, ...]] | None,
    use_threads: bool,
) -> list[dict[str, Any]]:
    batch_size = min(max(limit, 1), 4096)
    scanner = dataset.scanner(
        filter=expression,
        columns=selected,
        batch_size=batch_size,
        use_threads=use_threads,
    )
    rows: list[dict[str, Any]] = []
    for batch in scanner.to_batches():
        batch_rows = batch.to_pylist()
        if order_key is None:
            rows.extend(batch_rows)
            if len(rows) >= limit:
                return rows[:limit]
            continue
        rows.extend(batch_rows)
        rows.sort(key=order_key)
        del rows[limit:]
    return rows


__all__ = ["read_bounded_rows"]

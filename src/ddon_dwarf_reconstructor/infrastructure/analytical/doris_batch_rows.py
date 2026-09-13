"""Arrow-batch consumption at the Doris hydration boundary."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol, cast

import pyarrow as pa

from .doris_rows import restore_row


class _BatchStore(Protocol):
    """Minimal store surface needed by :func:`hydration_rows`."""

    def _rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
        operation: str = "family_rows",
    ) -> tuple[dict[str, Any], ...]: ...


def iter_record_batch_rows(
    batches: Iterable[pa.RecordBatch],
) -> Iterable[dict[str, Any]]:
    """Yield one row mapping without materializing an Arrow batch as Python rows."""
    for batch in batches:
        names = tuple(field.name for field in batch.schema)
        columns = tuple(batch.column(index) for index in range(batch.num_columns))
        for row_index in range(batch.num_rows):
            yield {
                name: column[row_index].as_py() for name, column in zip(names, columns, strict=True)
            }


def hydration_rows(
    store: _BatchStore,
    family: str,
    filters: Mapping[str, object] | None = None,
    *,
    columns: Sequence[str] = (),
    order_by: Sequence[str] = (),
    limit: int | None = None,
    table_name: str | None = None,
    operation: str = "family_rows",
) -> Iterable[dict[str, Any]]:
    """Read typed batches when available, with a compatibility row fallback."""
    reader = getattr(store, "_record_batches", None)
    query_reader = getattr(getattr(store, "_queries", None), "family_record_batches", None)
    if not callable(reader) or not callable(query_reader):
        return store._rows(
            family,
            filters,
            columns=columns,
            order_by=order_by,
            limit=limit,
            table_name=table_name,
            operation=operation,
        )
    batches = reader(
        family,
        filters,
        columns=columns,
        order_by=order_by,
        limit=limit,
        table_name=table_name,
        operation=operation,
    )
    return (
        restore_row(row) for row in iter_record_batch_rows(cast(Iterable[pa.RecordBatch], batches))
    )


__all__ = ["hydration_rows", "iter_record_batch_rows"]

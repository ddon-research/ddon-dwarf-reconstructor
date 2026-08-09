"""Result consumption and deterministic measurement helpers for Flight SQL."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, Protocol

from ..common.metrics import distribution, measure
from .adapter import FlightSqlCursor
from .specs import ParameterizedQuery

FetchMode = Literal["rows", "arrow_table", "record_batches", "reduce"]
ConnectionMode = Literal["reused", "cold"]


class QueryClient(Protocol):
    """Common cursor factory used by the two transport benchmark paths."""

    def cursor(self) -> FlightSqlCursor: ...

    def open(self) -> QueryClient: ...

    def close(self) -> None: ...

    def __enter__(self) -> QueryClient: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...


@dataclass(frozen=True, slots=True)
class QueryRun:
    """Internal query result retained for chaining related benchmark queries."""

    report: dict[str, Any]
    rows: tuple[tuple[Any, ...], ...]


def run_query_with_metrics(
    client: QueryClient,
    spec: ParameterizedQuery,
    mode: FetchMode,
    iterations: int,
    connection_mode: ConnectionMode = "reused",
) -> QueryRun:
    """Measure one cold query and reusable-connection warm samples."""
    cold = run_query_once(client, spec, mode, connection_mode)
    warm = [run_query_once(client, spec, mode, connection_mode) for _ in range(iterations)]
    report = {
        "query": spec.name,
        "mode": mode,
        "connection_mode": connection_mode,
        **spec.metadata,
        "status": "complete" if cold.report["row_count"] else "not_found",
        "matches": cold.report["row_count"],
        "result_digest": cold.report["result_digest"],
        "schema": cold.report["schema"],
        "arrow_batch_count": cold.report["arrow_batch_count"],
        "arrow_bytes": cold.report["arrow_bytes"],
        "cold": cold.report,
        "warm": _distribution_for(warm),
        "warm_result_stable": all(
            item.report["result_digest"] == cold.report["result_digest"] for item in warm
        ),
    }
    return QueryRun(report, cold.rows)


def run_query_once(
    client: QueryClient,
    spec: ParameterizedQuery,
    mode: FetchMode,
    connection_mode: ConnectionMode = "reused",
) -> QueryRun:
    """Execute and consume one result while separating query, fetch, and conversion phases."""
    if connection_mode == "cold":
        client.close()
        client.open()
    started = perf_counter()
    with client.cursor() as cursor:
        session_metrics = None
        session_sql = spec.metadata.get("session_sql")
        if isinstance(session_sql, str):
            _, session_metrics = measure(lambda: cursor.execute(session_sql))
        _, execute_metrics = measure(lambda: cursor.execute(spec.sql, spec.params))
        description = cursor.description
        raw, fetch_metrics = measure(lambda: _fetch_result(cursor, mode))
        materialized, conversion_metrics = measure(
            lambda: _materialize_result(raw, mode, description, spec.metadata)
        )
    report = {
        "wall_seconds": perf_counter() - started,
        "connection_mode": connection_mode,
        "session": session_metrics,
        "execute": execute_metrics,
        "fetch": fetch_metrics,
        "conversion": conversion_metrics,
        **materialized[1],
    }
    return QueryRun(report, materialized[0])


def _fetch_result(cursor: FlightSqlCursor, mode: FetchMode) -> Any:
    if mode == "rows":
        return tuple(tuple(row) for row in cursor.fetchall())
    if mode == "arrow_table":
        return cursor.fetch_arrow_table()
    reader = cursor.fetch_record_batch()
    batches = []
    while True:
        try:
            batches.append(reader.read_next_batch())
        except StopIteration:
            break
    return tuple(batches)


def _materialize_result(
    raw: Any,
    mode: FetchMode,
    description: Any,
    metadata: dict[str, object],
) -> tuple[tuple[tuple[Any, ...], ...], dict[str, Any]]:
    if mode == "rows":
        rows = tuple(raw)
        return rows, _row_metadata(rows, _description_names(description))
    if mode == "arrow_table":
        return _materialize_arrow_table(raw)
    batches = tuple(raw)
    if mode == "reduce":
        return (), _reduce_metadata(batches, str(metadata.get("reducer", "")))
    return _materialize_record_batches(batches)


def _materialize_arrow_table(table: Any) -> tuple[tuple[tuple[Any, ...], ...], dict[str, Any]]:
    schema = tuple(field.name for field in table.schema)
    rows = tuple(tuple(row.get(name) for name in schema) for row in table.to_pylist())
    return rows, _arrow_metadata(table, (table,), rows, schema)


def _materialize_record_batches(
    batches: tuple[Any, ...],
) -> tuple[tuple[tuple[Any, ...], ...], dict[str, Any]]:
    schema = tuple(field.name for field in batches[0].schema) if batches else ()
    rows = tuple(
        tuple(row.get(name) for name in schema) for batch in batches for row in batch.to_pylist()
    )
    return rows, _arrow_metadata(None, batches, rows, schema)


def _description_names(description: Any) -> tuple[str, ...]:
    return tuple(str(column[0]) for column in (description or ()))


def _row_metadata(rows: tuple[tuple[Any, ...], ...], schema: tuple[str, ...]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "schema": schema,
        "result_digest": digest(rows),
        "arrow_batch_count": None,
        "arrow_bytes": None,
        "peak_message_size_bytes": None,
        "peak_message_size_status": "not_observed",
    }


def _arrow_metadata(
    table: Any,
    batches: Iterable[Any],
    rows: tuple[tuple[Any, ...], ...],
    schema: tuple[str, ...],
) -> dict[str, Any]:
    batch_values = tuple(batches)
    names = schema or (tuple(field.name for field in table.schema) if table is not None else ())
    return {
        "row_count": len(rows),
        "schema": names,
        "result_digest": digest(rows),
        "arrow_batch_count": len(batch_values),
        "arrow_bytes": sum(int(batch.nbytes) for batch in batch_values),
        "peak_message_size_bytes": None,
        "peak_message_size_status": "not_observed",
    }


def _reduce_metadata(batches: Iterable[Any], reducer: str = "") -> dict[str, Any]:
    batch_values = tuple(batches)
    schema = tuple(field.name for field in batch_values[0].schema) if batch_values else ()
    row_count = sum(int(batch.num_rows) for batch in batch_values)
    null_counts = {
        name: sum(int(batch.column(index).null_count) for batch in batch_values)
        for index, name in enumerate(schema)
    }
    reduction: dict[str, Any] = {"row_count": row_count, "null_counts": null_counts}
    if reducer == "count_by_first_column" and schema:
        reduction.update(
            {
                "reducer": reducer,
                "counts": _first_column_counts(batch_values, schema[0]),
            }
        )
    return {
        "row_count": row_count,
        "schema": schema,
        "result_digest": digest(reduction),
        "arrow_batch_count": len(batch_values),
        "arrow_bytes": sum(int(batch.nbytes) for batch in batch_values),
        "peak_message_size_bytes": None,
        "peak_message_size_status": "not_observed",
        "reduction": reduction,
    }


def _first_column_counts(batches: tuple[Any, ...], column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for batch in batches:
        for row in batch.to_pylist():
            key = json.dumps(_canonical(row.get(column)), sort_keys=True, ensure_ascii=True)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _distribution_for(samples: list[QueryRun]) -> dict[str, Any]:
    return {
        **distribution([item.report for item in samples]),
        "execute": distribution([item.report["execute"] for item in samples]),
        "fetch": distribution([item.report["fetch"] for item in samples]),
        "conversion": distribution([item.report["conversion"] for item in samples]),
    }


def digest(value: object) -> str:
    """Hash values without losing bytes, decimals, timestamps, or nested order."""
    payload = json.dumps(
        _canonical(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return {"bytes_base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (date, datetime, time)):
        return {"iso": value.isoformat()}
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return {"repr": repr(value)}

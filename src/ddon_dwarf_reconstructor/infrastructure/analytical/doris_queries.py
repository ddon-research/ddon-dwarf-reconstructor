"""Small, parameterized query boundary for the Doris serving projection."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, TypeGuard

import pyarrow as pa

from ...core.observability import get_logger, log_event
from .doris import DorisConfig
from .doris_diagnostics_transport import DorisDiagnosticTransport
from .doris_diagnostics_utils import (
    _payload_text,
    _profile_json,
    _profile_payload_summary,
    profile_matches_query_id,
)
from .doris_layout import _family_table
from .doris_optimization import DorisQueryTracer
from .doris_optimization_utils import profile_metrics as _profile_metrics
from .doris_query_batches import cursor_record_batches
from .doris_schema import _FAMILY_COLUMNS

logger = get_logger(__name__)


class _DorisCursor(Protocol):
    """Subset of the DB-API cursor used by the runtime adapter."""

    description: Sequence[Sequence[object]]

    def __enter__(self) -> _DorisCursor: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    def execute(self, operation: str, params: Sequence[object] = ()) -> object: ...

    def fetchall(self) -> Sequence[Sequence[object]]: ...

    def fetchmany(self, size: int) -> Sequence[Sequence[object]]: ...


class _DorisConnection(Protocol):
    """Subset of the DB-API connection needed by :class:`DorisQueryExecutor`."""

    def cursor(self) -> _DorisCursor: ...


@dataclass(frozen=True, slots=True)
class BoundedRows:
    """Rows returned by a bounded query, including truncation evidence."""

    rows: tuple[dict[str, object], ...]
    truncated: bool


class DorisQueryExecutor:
    """Execute source-bound, read-only queries against Doris.

    Identifiers come only from the analytical layout helpers. Values are always
    sent through DB-API parameters so symbol names and source identities cannot
    become SQL syntax.
    """

    def __init__(
        self,
        connection: _DorisConnection,
        config: DorisConfig,
        source_id: str,
    ) -> None:
        self._connection = connection
        self._config = config
        self._source_id = source_id
        self._closed = False
        self._definition_lookup_table = config.effective_definition_lookup_table
        self._tracer = (
            DorisQueryTracer(
                source_id,
                config,
                config.query_trace,
                profile_fetcher=lambda query_id, timeout: _fetch_generation_profile(
                    config, query_id, timeout
                ),
            )
            if config.query_trace is not None
            else None
        )

    def close(self) -> None:
        """Flush optional query evidence owned by this executor."""
        if self._closed:
            return
        self._closed = True
        if self._tracer is not None:
            self._tracer.close()

    def find_definition_rows(
        self,
        name: str,
        *,
        tags: Sequence[str] = (),
        limit: int = 1001,
    ) -> tuple[dict[str, object], ...]:
        """Return deterministic definition-index rows for one source symbol."""

        if limit < 1:
            raise ValueError("limit must be positive")

        return self.find_definition_rows_bounded(name, tags=tags, limit=limit).rows

    def find_definition_rows_bounded(
        self,
        name: str,
        *,
        tags: Sequence[str] = (),
        limit: int = 1001,
    ) -> BoundedRows:
        """Return definition rows and preserve whether the bound was reached."""

        if limit < 1:
            raise ValueError("limit must be positive")

        filters: dict[str, object] = {
            "index_type": "definition",
            "name": name,
        }
        if tags:
            filters["tag"] = tuple(tags)
        rows = self.family_rows(
            "index",
            filters,
            order_by=("unit_offset", "die_offset"),
            limit=limit,
            table_name=self._definition_lookup_table,
        )
        return BoundedRows(rows=rows, truncated=len(rows) >= limit)

    def find_definition_rows_complete(
        self,
        name: str,
        *,
        tags: Sequence[str] = (),
        max_rows: int = 10_000,
    ) -> BoundedRows:
        """Read a complete candidate window with an explicit safety ceiling.

        The normal lookup is intentionally cheap and bounded at 1,001 rows.
        Primary-definition selection may need more rows because DWARF repeats
        the same source name in many compilation units.  This path keeps the
        transfer bounded while distinguishing a complete result from a safety
        ceiling that was actually exceeded.
        """
        if max_rows < 1:
            raise ValueError("max_rows must be positive")

        filters: dict[str, object] = {
            "index_type": "definition",
            "name": name,
        }
        if tags:
            filters["tag"] = tuple(tags)
        rows = self.family_rows(
            "index",
            filters,
            order_by=("unit_offset", "die_offset"),
            limit=max_rows + 1,
            table_name=self._definition_lookup_table,
            operation="find_definitions_complete",
        )
        return BoundedRows(rows=rows[:max_rows], truncated=len(rows) > max_rows)

    def find_definition_tags(self, name: str) -> tuple[str, ...]:
        """Return the complete set of aggregate tags for one source name."""
        table = _qualified_table(
            self._config,
            "index",
            table_name=self._definition_lookup_table,
        )
        query = (
            f"SELECT `tag`, COUNT(*) AS `definition_count` FROM {table} "
            "WHERE `source_id` = %s AND `index_type` = %s AND `name` = %s "
            "GROUP BY `tag` ORDER BY `tag`"
        )
        rows = self._fetch_rows(
            query,
            (self._source_id, "definition", name),
            family="index",
            operation="definition_tags",
        )
        tags: list[str] = []
        for row in rows:
            tag = row.get("tag")
            if isinstance(tag, str) and tag:
                tags.append(tag)
        return tuple(tags)

    def find_method_implementation_rows(
        self,
        declaration_offsets: Sequence[int],
        *,
        limit: int = 100_000,
    ) -> BoundedRows:
        """Return a deterministic, bounded implementation-index batch."""
        offsets = tuple(
            sorted({offset for offset in declaration_offsets if isinstance(offset, int)})
        )
        if not offsets:
            return BoundedRows((), False)
        if limit < 1:
            raise ValueError("limit must be positive")
        rows = self.family_rows(
            "index",
            {
                "index_type": "method_implementation",
                "target_offset": offsets,
                "resolution_status": "complete",
            },
            columns=(
                "source_id",
                "unit_offset",
                "die_offset",
                "index_type",
                "name",
                "tag",
                "target_offset",
                "resolution_status",
            ),
            order_by=("target_offset", "unit_offset", "die_offset"),
            limit=limit + 1,
            table_name=self._config.method_lookup_table,
            operation="method_implementation_rows_batch",
        )
        return BoundedRows(rows[:limit], len(rows) > limit)

    def family_rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        operation: str = "family_rows",
        table_name: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Return source-bound rows using only parameterized filter values."""
        _validate_limit(limit)
        selected = ", ".join(_identifier(column) for column in columns)
        if not selected:
            selected = "*" if table_name is not None else _all_columns(family)
        conditions, params = _filter_conditions(self._source_id, filters)
        table = _qualified_table(self._config, family, table_name=table_name)
        query = f"SELECT {selected} FROM {table} WHERE {' AND '.join(conditions)}"
        query = _append_order_and_limit(query, order_by, limit)
        return self._fetch_rows(query, params, family=family, operation=operation)

    def family_record_batches(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        operation: str = "family_record_batches",
        table_name: str | None = None,
        batch_size: int = 512,
    ) -> tuple[pa.RecordBatch, ...]:
        """Return a bounded typed batch stream from one source-bound query."""
        _validate_limit(limit)
        _validate_limit(batch_size)
        selected = ", ".join(_identifier(column) for column in columns)
        if not selected:
            selected = "*" if table_name is not None else _all_columns(family)
        conditions, params = _filter_conditions(self._source_id, filters)
        table = _qualified_table(self._config, family, table_name=table_name)
        query = f"SELECT {selected} FROM {table} WHERE {' AND '.join(conditions)}"
        query = _append_order_and_limit(query, order_by, limit)
        return self._fetch_record_batches(
            query,
            params,
            family=family,
            operation=operation,
            batch_size=batch_size,
        )

    def frame_rows_overlapping(
        self,
        start_address: int,
        end_address: int,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Push one CFI range join into Doris instead of scanning its result in Python."""
        if end_address <= start_address:
            return ()
        _validate_limit(limit)
        selected = ", ".join(_identifier(column) for column in columns)
        if not selected:
            selected = _all_columns("frame")
        table = _qualified_table(self._config, "frame")
        query = (
            f"SELECT {selected} FROM {table} WHERE `source_id` = %s "
            "AND `initial_address` < %s "
            "AND `initial_address` + `address_range` > %s"
        )
        query = _append_order_and_limit(query, order_by, limit)
        return self._fetch_rows(
            query,
            (self._source_id, end_address, start_address),
            family="frame",
            operation="frame_rows_overlapping",
        )

    def _fetch_rows(
        self,
        query: str,
        params: Sequence[object],
        *,
        family: str,
        operation: str,
    ) -> tuple[dict[str, object], ...]:
        execute_started = perf_counter()
        execute_seconds = 0.0
        fetch_seconds = 0.0
        rows: Sequence[Sequence[object]] = ()
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query, params)
                execute_seconds = perf_counter() - execute_started
                fetch_started = perf_counter()
                rows = cursor.fetchall()
                fetch_seconds = perf_counter() - fetch_started
                columns = tuple(str(column[0]) for column in cursor.description)
        except Exception as error:
            execute_seconds = execute_seconds or perf_counter() - execute_started
            self._record_trace(
                query,
                family=family,
                operation=operation,
                execute_seconds=execute_seconds,
                fetch_seconds=fetch_seconds,
                rows=(),
                error=error,
            )
            raise
        self._record_trace(
            query,
            family=family,
            operation=operation,
            execute_seconds=execute_seconds,
            fetch_seconds=fetch_seconds,
            rows=rows,
        )
        return tuple(dict(zip(columns, row, strict=True)) for row in rows)

    def _fetch_record_batches(
        self,
        query: str,
        params: Sequence[object],
        *,
        family: str,
        operation: str,
        batch_size: int,
    ) -> tuple[pa.RecordBatch, ...]:
        execute_started = perf_counter()
        execute_seconds = 0.0
        fetch_seconds = 0.0
        batches: tuple[pa.RecordBatch, ...] = ()
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query, params)
                execute_seconds = perf_counter() - execute_started
                columns = tuple(str(column[0]) for column in cursor.description)
                fetch_started = perf_counter()
                batches = cursor_record_batches(cursor, columns, batch_size, family)
                fetch_seconds = perf_counter() - fetch_started
        except Exception as error:
            execute_seconds = execute_seconds or perf_counter() - execute_started
            self._record_trace(
                query,
                family=family,
                operation=operation,
                execute_seconds=execute_seconds,
                fetch_seconds=fetch_seconds,
                rows=(),
                result_rows=0,
                error=error,
            )
            raise
        self._record_trace(
            query,
            family=family,
            operation=operation,
            execute_seconds=execute_seconds,
            fetch_seconds=fetch_seconds,
            rows=(),
            result_rows=sum(batch.num_rows for batch in batches),
        )
        return tuple(batches)

    def _record_trace(
        self,
        query: str,
        *,
        family: str,
        operation: str,
        execute_seconds: float,
        fetch_seconds: float,
        rows: Sequence[Sequence[object]],
        result_rows: int | None = None,
        error: Exception | None = None,
    ) -> None:
        """Keep optional tracing from masking query results or failures."""
        if self._tracer is None:
            return
        try:
            self._tracer.record(
                self._connection,
                sql=query,
                family=family,
                operation=operation,
                execute_seconds=execute_seconds,
                fetch_seconds=fetch_seconds,
                rows=rows,
                result_rows=result_rows,
                error=error,
            )
        except Exception as trace_error:
            log_event(
                logger,
                logging.WARNING,
                "doris_query_trace_failed",
                operation=operation,
                exc_info=trace_error,
            )


def _qualified_table(config: DorisConfig, family: str, *, table_name: str | None = None) -> str:
    table = table_name or _family_table(config.table, family)
    return f"{_identifier(config.database)}.{_identifier(table)}"


def _validate_limit(limit: int | None) -> None:
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")


def _filter_conditions(
    source_id: str,
    filters: Mapping[str, object] | None,
) -> tuple[list[str], list[object]]:
    conditions = ["source_id = %s"]
    params: list[object] = [source_id]
    for column, value in (filters or {}).items():
        condition, values = _filter_clause(column, value)
        conditions.append(condition)
        params.extend(values)
    return conditions, params


def _filter_clause(column: str, value: object) -> tuple[str, tuple[object, ...]]:
    identifier = _identifier(column)
    if value is None:
        return f"{identifier} IS NULL", ()
    if not _is_sequence_value(value):
        return f"{identifier} = %s", (value,)
    values = tuple(value)
    if not values:
        return "1 = 0", ()
    placeholders = ", ".join("%s" for _ in values)
    return f"{identifier} IN ({placeholders})", values


def _append_order_and_limit(
    query: str,
    order_by: Sequence[str],
    limit: int | None,
) -> str:
    if order_by:
        query += " ORDER BY " + ", ".join(_identifier(column) for column in order_by)
    if limit is not None:
        query += f" LIMIT {limit}"
    return query


def _identifier(value: str) -> str:
    if not value or not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{value}`"


def _all_columns(family: str) -> str:
    columns = tuple(
        definition.split(maxsplit=1)[0].strip("`") for definition in _FAMILY_COLUMNS[family]
    )
    return ", ".join(_identifier(column) for column in columns)


def _is_sequence_value(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _fetch_generation_profile(
    config: DorisConfig, query_id: str, timeout_seconds: float
) -> tuple[str, Mapping[str, object], Mapping[str, object], object | None, str | None]:
    """Fetch one FE-local profile for the traced generation query immediately."""
    transport = DorisDiagnosticTransport(config, timeout_seconds=timeout_seconds)
    result = transport.profile(query_id, full=True)
    text = _payload_text(result.payload, result.raw_text)
    if result.status != "observed" or not text.strip():
        return result.status, {}, {}, None, result.error or "Doris profile was not returned"
    if not profile_matches_query_id(result.payload, text, query_id):
        return "partial", {}, {}, None, "profile did not contain requested query ID"
    payload = _profile_json(result, text)
    summary = _profile_payload_summary(result.payload, text)
    return "observed", summary, _profile_metrics(summary), payload, None

"""Opt-in Arrow Flight SQL access for analytical Doris benchmarks.

The normal analytical store remains on the PyMySQL path.  This module owns the
optional ADBC dependency and deliberately exposes the DB-API cursor so the
benchmark can measure row conversion, full Arrow materialization, and streamed
RecordBatch consumption independently.
"""

from __future__ import annotations

import importlib.metadata
import math
import re
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Protocol

from ...doris import DorisConfig
from ...optional import import_optional


class FlightSqlCursor(Protocol):
    """Small cursor surface shared by ADBC and benchmark test doubles."""

    @property
    def description(self) -> Any: ...

    def __enter__(self) -> FlightSqlCursor: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    def execute(self, operation: str, parameters: tuple[object, ...] = ()) -> Any: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...

    def fetch_arrow_table(self) -> Any: ...

    def fetch_record_batch(self) -> Any: ...


def render_unparameterized_sql(operation: str, parameters: tuple[object, ...]) -> str:
    """Render qmark values as checked SQL literals for the explicit fallback.

    Doris's Flight producer accepts complete SQL through ``CommandStatementQuery``
    but does not implement the parameter upload operation.  This renderer is
    therefore limited to the benchmark fallback and rejects unsupported values
    instead of using ``repr`` or interpolating arbitrary objects.
    """
    parts = operation.split("?")
    if len(parts) - 1 != len(parameters):
        raise ValueError(
            f"qmark/value count mismatch: SQL has {len(parts) - 1} placeholders, "
            f"received {len(parameters)} values"
        )
    rendered: list[str] = []
    for index, part in enumerate(parts[:-1]):
        rendered.extend((part, _sql_literal(parameters[index])))
    rendered.append(parts[-1])
    return "".join(rendered)


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"'{_escape_sql_string(value)}'"
    if isinstance(value, bytes):
        return f"X'{value.hex()}'"
    if isinstance(value, (date, datetime, time)):
        text = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
        return f"'{_escape_sql_string(text)}'"
    return _sql_scalar_literal(value)


def _sql_scalar_literal(value: object) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not valid SQL literals")
        return repr(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite decimals are not valid SQL literals")
        return format(value, "f")
    raise TypeError(f"unsupported SQL literal type: {type(value).__name__}")


def _escape_sql_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\x00", "\\0")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\x1a", "\\Z")
        .replace("'", "''")
    )


class _UnparameterizedFlightSqlCursor:
    """Cursor proxy that sends complete SQL through Doris's statement path."""

    def __init__(self, cursor: FlightSqlCursor) -> None:
        self._cursor = cursor

    @property
    def description(self) -> Any:
        return self._cursor.description

    def __enter__(self) -> _UnparameterizedFlightSqlCursor:
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._cursor.__exit__(exc_type, exc_value, traceback)

    def execute(self, operation: str, parameters: tuple[object, ...] = ()) -> Any:
        return self._cursor.execute(render_unparameterized_sql(operation, parameters))

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._cursor.fetchall()

    def fetch_arrow_table(self) -> Any:
        return self._cursor.fetch_arrow_table()

    def fetch_record_batch(self) -> Any:
        return self._cursor.fetch_record_batch()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class FlightSqlConnection(Protocol):
    """Connection surface needed by :class:`DorisFlightSqlClient`."""

    adbc_connection: Any

    def cursor(self) -> FlightSqlCursor: ...

    def close(self) -> None: ...


class DorisFlightSqlClient:
    """Open one reusable ADBC Flight SQL connection to a Doris FE."""

    def __init__(self, config: DorisConfig) -> None:
        self._config = config
        self._connection: FlightSqlConnection | None = None
        self._driver_versions: dict[str, str] = {}
        self._unparameterized_fallback = False

    @property
    def endpoint(self) -> str:
        """Return the configured FE endpoint without exposing credentials."""
        return self._config.flight_sql_uri or (
            f"grpc://{self._config.flight_sql_host}:{self._config.flight_sql_port}"
        )

    @property
    def driver_versions(self) -> Mapping[str, str]:
        """Return package versions captured when the connection was opened."""
        return dict(self._driver_versions)

    @property
    def execution_mode(self) -> str:
        """Return the SQL execution mode used by this benchmark client."""
        return "unparameterized_fallback" if self._unparameterized_fallback else "qmark"

    def open(self) -> DorisFlightSqlClient:
        """Load ADBC lazily and establish a bounded, authenticated connection."""
        if self._connection is not None:
            return self
        _validate_endpoint(self.endpoint)
        manager = import_optional("adbc_driver_manager", "flight-sql")
        flight = import_optional("adbc_driver_flightsql", "flight-sql")
        dbapi = import_optional("adbc_driver_flightsql.dbapi", "flight-sql")
        db_kwargs = {
            manager.DatabaseOptions.USERNAME.value: self._config.user,
            manager.DatabaseOptions.PASSWORD.value: self._config.password,
            flight.DatabaseOptions.WITH_MAX_MSG_SIZE.value: str(
                self._config.flight_sql_max_message_size
            ),
        }
        connection = dbapi.connect(uri=self.endpoint, db_kwargs=db_kwargs, autocommit=True)
        try:
            connection.adbc_connection.set_options(
                **{
                    flight.ConnectionOptions.TIMEOUT_QUERY.value: (
                        self._config.flight_sql_query_timeout_seconds
                    ),
                    flight.ConnectionOptions.TIMEOUT_FETCH.value: (
                        self._config.flight_sql_fetch_timeout_seconds
                    ),
                }
            )
        except BaseException:
            connection.close()
            raise
        self._connection = connection
        self._driver_versions = _package_versions()
        return self

    def cursor(self) -> FlightSqlCursor:
        """Return a cursor from the explicitly opened connection."""
        if self._connection is None:
            raise RuntimeError("Flight SQL client is not open")
        cursor = self._connection.cursor()
        if self._unparameterized_fallback:
            return _UnparameterizedFlightSqlCursor(cursor)
        return cursor

    def enable_unparameterized_fallback(self) -> None:
        """Reconnect and switch this explicit benchmark client to complete SQL."""
        if self._connection is None:
            raise RuntimeError("Flight SQL client is not open")
        self._unparameterized_fallback = True
        self.close()
        self.open()

    def close(self) -> None:
        """Close the Flight connection and release Doris server-side state."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> DorisFlightSqlClient:
        return self.open()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _validate_endpoint(endpoint: str) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/]+", endpoint):
        raise ValueError(f"Invalid Flight SQL endpoint: {endpoint!r}")


def _package_versions() -> dict[str, str]:
    """Capture versions without importing optional modules a second time."""
    versions: dict[str, str] = {}
    for distribution in ("adbc-driver-manager", "adbc-driver-flightsql", "pyarrow"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "unavailable"
    return versions

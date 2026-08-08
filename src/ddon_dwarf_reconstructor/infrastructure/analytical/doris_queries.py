"""Small, parameterized query boundary for the Doris serving projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, TypeGuard

from .doris import DorisConfig
from .doris_layout import _family_table


class _DorisCursor(Protocol):
    """Subset of the DB-API cursor used by the runtime adapter."""

    description: Sequence[Sequence[object]]

    def __enter__(self) -> _DorisCursor: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    def execute(self, operation: str, params: Sequence[object] = ()) -> object: ...

    def fetchall(self) -> Sequence[Sequence[object]]: ...


class _DorisConnection(Protocol):
    """Subset of the DB-API connection needed by :class:`DorisQueryExecutor`."""

    def cursor(self) -> _DorisCursor: ...


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

        filters: dict[str, object] = {
            "index_type": "definition",
            "name": name,
        }
        if tags:
            filters["tag"] = tuple(tags)
        return self.family_rows(
            "index",
            filters,
            order_by=("unit_offset", "die_offset"),
            limit=limit,
        )

    def family_rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Return source-bound rows using only parameterized filter values."""
        _validate_limit(limit)
        selected = ", ".join(_identifier(column) for column in columns) or "*"
        conditions, params = _filter_conditions(self._source_id, filters)
        table = _qualified_table(self._config, family)
        query = f"SELECT {selected} FROM {table} WHERE {' AND '.join(conditions)}"
        query = _append_order_and_limit(query, order_by, limit)
        return self._fetch_rows(query, params)

    def _fetch_rows(
        self,
        query: str,
        params: Sequence[object],
    ) -> tuple[dict[str, object], ...]:
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = tuple(str(column[0]) for column in cursor.description)
        return tuple(dict(zip(columns, row, strict=True)) for row in rows)


def _qualified_table(config: DorisConfig, family: str) -> str:
    return f"{_identifier(config.database)}.{_identifier(_family_table(config.table, family))}"


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


def _is_sequence_value(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))

"""Small, parameterized query boundary for the Doris serving projection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .doris import DorisConfig
from .doris_layout import _family_table


class _DorisCursor(Protocol):
    """Subset of the DB-API cursor used by the runtime adapter."""

    description: Sequence[Sequence[object]]

    def __enter__(self) -> "_DorisCursor": ...

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

        conditions = [
            "source_id = %s",
            "index_type = %s",
            "name = %s",
        ]
        params: list[object] = [self._source_id, "definition", name]
        if tags:
            placeholders = ", ".join("%s" for _ in tags)
            conditions.append(f"tag IN ({placeholders})")
            params.extend(tags)

        table = _family_table(self._config.table, "index")
        query = (
            "SELECT unit_offset, die_offset, tag, name, target_offset, "
            "resolution_status "
            f"FROM {table} WHERE {' AND '.join(conditions)} "
            "ORDER BY unit_offset, die_offset "
            f"LIMIT {limit}"
        )
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
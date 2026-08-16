"""Source-independent SQL connection boundary for the Doris adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .doris_config import DorisConfig
from .optional import import_optional

DependencyLoader = Callable[[str, str], Any]


class DorisConnectionError(ConnectionError):
    """A Doris connection failure with the exact configured target attached."""

    def __init__(
        self,
        config: DorisConfig,
        database: str | None,
        cause: Exception,
    ) -> None:
        self.endpoint = config.sql_endpoint
        self.database = database
        self.user = config.user
        selected_database = database if database is not None else "<not selected>"
        message = (
            f"Doris SQL connection failed for {config.sql_endpoint} "
            f"(database={selected_database!r}, user={config.user!r}); "
            "set DDON_DORIS_SQL_HOST/DDON_DORIS_SQL_PORT to the published FE endpoint. "
            f"{type(cause).__name__}: {cause}"
        )
        super().__init__(message)


def connect_sql(
    config: DorisConfig,
    *,
    database: str | None = None,
    dependency_loader: DependencyLoader = import_optional,
) -> Any:
    """Open one PyMySQL connection and preserve endpoint context on failure.

    The loader is injectable so adapter tests can replace the optional
    dependency without importing or requiring a live database. No alternate
    endpoint is probed implicitly: the configured host and port are the
    source-bound connection contract.
    """
    pymysql = dependency_loader("pymysql", "analytical")
    arguments: dict[str, object] = {
        "host": config.sql_host,
        "port": config.sql_port,
        "user": config.user,
        "password": config.password,
        "autocommit": True,
        "connect_timeout": config.sql_connect_timeout_seconds,
        "read_timeout": config.sql_read_timeout_seconds,
        "write_timeout": config.sql_write_timeout_seconds,
    }
    if database is not None:
        arguments["database"] = database
    try:
        return pymysql.connect(**arguments)
    except Exception as error:
        raise DorisConnectionError(config, database, error) from error


__all__ = ["DorisConnectionError", "connect_sql"]

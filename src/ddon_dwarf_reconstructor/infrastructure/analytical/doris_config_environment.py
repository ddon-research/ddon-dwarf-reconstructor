"""Environment-derived Doris connection settings."""

from __future__ import annotations

import os
from typing import Protocol, TypedDict


class FlightEnvironmentValues(TypedDict):
    """Typed keyword values accepted by ``DorisConfig``."""

    flight_sql_host: str
    flight_sql_port: int
    flight_sql_uri: str | None
    flight_sql_fe_public_host: str | None
    flight_sql_public_host: str | None
    flight_sql_public_port: int
    flight_sql_max_message_size: int
    flight_sql_query_timeout_seconds: float
    flight_sql_fetch_timeout_seconds: float


class FlightDefaults(Protocol):
    """Doris configuration fields needed for Flight SQL defaults."""

    @property
    def flight_sql_host(self) -> str: ...

    @property
    def flight_sql_port(self) -> int: ...

    @property
    def flight_sql_uri(self) -> str | None: ...

    @property
    def flight_sql_fe_public_host(self) -> str | None: ...

    @property
    def flight_sql_public_host(self) -> str | None: ...

    @property
    def flight_sql_public_port(self) -> int: ...

    @property
    def flight_sql_max_message_size(self) -> int: ...

    @property
    def flight_sql_query_timeout_seconds(self) -> float: ...

    @property
    def flight_sql_fetch_timeout_seconds(self) -> float: ...


def flight_environment_values(defaults: FlightDefaults) -> FlightEnvironmentValues:
    """Return Flight SQL settings for a Doris configuration constructor."""
    return {
        "flight_sql_host": os.getenv("DDON_DORIS_FLIGHT_SQL_HOST", defaults.flight_sql_host),
        "flight_sql_port": int(
            os.getenv("DDON_DORIS_FLIGHT_SQL_PORT", str(defaults.flight_sql_port))
        ),
        "flight_sql_uri": os.getenv("DDON_DORIS_FLIGHT_SQL_URI", defaults.flight_sql_uri),
        "flight_sql_fe_public_host": os.getenv(
            "DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST", defaults.flight_sql_fe_public_host
        ),
        "flight_sql_public_host": os.getenv(
            "DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST", defaults.flight_sql_public_host
        ),
        "flight_sql_public_port": int(
            os.getenv("DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT", str(defaults.flight_sql_public_port))
        ),
        "flight_sql_max_message_size": int(
            os.getenv(
                "DDON_DORIS_FLIGHT_SQL_MAX_MESSAGE_SIZE",
                str(defaults.flight_sql_max_message_size),
            )
        ),
        "flight_sql_query_timeout_seconds": float(
            os.getenv(
                "DDON_DORIS_FLIGHT_SQL_QUERY_TIMEOUT_SECONDS",
                str(defaults.flight_sql_query_timeout_seconds),
            )
        ),
        "flight_sql_fetch_timeout_seconds": float(
            os.getenv(
                "DDON_DORIS_FLIGHT_SQL_FETCH_TIMEOUT_SECONDS",
                str(defaults.flight_sql_fetch_timeout_seconds),
            )
        ),
    }


__all__ = ["flight_environment_values"]

"""Immutable Doris connection, serving, and environment configuration."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import TypedDict

from .doris_config_environment import flight_environment_values
from .doris_ddl import _native_sql
from .doris_layout import default_name_lookup_table
from .doris_optimization import DorisQueryTraceConfig

__all__ = ["DorisConfig"]


class _SqlTimeoutEnvironmentValues(TypedDict):
    sql_connect_timeout_seconds: float
    sql_read_timeout_seconds: float
    sql_write_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class DorisConfig:
    """Local Doris connection and table settings."""

    http_url: str = "http://127.0.0.1:8030"
    stream_load_url: str = "http://127.0.0.1:8040"
    sql_host: str = "127.0.0.1"
    sql_port: int = 9030
    database: str = "dwarf"
    user: str = "root"
    password: str = ""
    table: str = "dwarf_records"
    definition_lookup_table: str | None = None
    name_lookup_table: str | None = None
    method_lookup_table: str | None = None
    die_lookup_table: str | None = None
    flight_sql_host: str = "127.0.0.1"
    flight_sql_port: int = 8070
    flight_sql_uri: str | None = None
    flight_sql_fe_public_host: str | None = None
    flight_sql_public_host: str | None = None
    flight_sql_public_port: int = 8050
    flight_sql_max_message_size: int = 16 * 1024 * 1024
    flight_sql_query_timeout_seconds: float = 30.0
    flight_sql_fetch_timeout_seconds: float = 300.0
    analyze_after_load: bool = True
    analyze_wait_seconds: float = 0.0
    stream_load_workers: int = 1
    statistics_policy: str = "selective"
    reference_prefetch: str = "lazy"
    attribute_projection: str = "serving"
    child_tag_filter: str = "all"
    hydration_scope: str = "global"
    serving_variant_id: str = "canonical"
    stream_load_connect_timeout_seconds: float = 15.0
    stream_load_read_timeout_seconds: float = 300.0
    stream_load_write_timeout_seconds: float = 300.0
    sql_connect_timeout_seconds: float = 15.0
    sql_read_timeout_seconds: float = 300.0
    sql_write_timeout_seconds: float = 300.0
    publication_verify_timeout_seconds: float = 60.0
    query_trace: DorisQueryTraceConfig | None = None
    capture_statistics_evidence: bool = False

    def __post_init__(self) -> None:
        if self.analyze_wait_seconds < 0:
            raise ValueError("analyze_wait_seconds must not be negative")
        if self.stream_load_workers < 1:
            raise ValueError("stream_load_workers must be positive")
        _validate_stream_load_timeouts(self)
        if self.publication_verify_timeout_seconds <= 0:
            raise ValueError("publication_verify_timeout_seconds must be positive")
        _validate_sql_timeouts(self)
        if self.statistics_policy not in {"all", "selective"}:
            raise ValueError("statistics_policy must be all or selective")
        if self.reference_prefetch not in {"eager", "lazy"}:
            raise ValueError("reference_prefetch must be eager or lazy")
        if self.attribute_projection not in {"full", "serving"}:
            raise ValueError("attribute_projection must be full or serving")
        if self.child_tag_filter not in {"all", "targeted"}:
            raise ValueError("child_tag_filter must be all or targeted")
        if self.hydration_scope not in {"global", "unit"}:
            raise ValueError("hydration_scope must be global or unit")
        if not self.serving_variant_id.strip():
            raise ValueError("serving_variant_id must not be empty")
        self._validate_flight_settings()

    def ddl_sha256(self) -> str:
        """Return the hash of the exact canonical DDL emitted by this configuration."""
        ddl = "\n".join(_native_sql(self))
        return hashlib.sha256(ddl.encode("utf-8")).hexdigest()

    @property
    def effective_definition_lookup_table(self) -> str:
        """Return the source/name table used for definition lookup by default."""
        return self.definition_lookup_table or default_name_lookup_table(self.table)

    @property
    def effective_name_lookup_table(self) -> str:
        """Return the source/name table used for name lookup by default."""
        return self.name_lookup_table or default_name_lookup_table(self.table)

    @property
    def uses_promoted_name_lookup(self) -> bool:
        """Whether this configuration owns the canonical source/name projection."""
        return (
            self.serving_variant_id == "canonical"
            and self.effective_name_lookup_table == default_name_lookup_table(self.table)
        )

    def _validate_flight_settings(self) -> None:
        if self.flight_sql_port < 1 or self.flight_sql_port > 65535:
            raise ValueError("flight_sql_port must be a valid TCP port")
        if self.flight_sql_public_port < 1 or self.flight_sql_public_port > 65535:
            raise ValueError("flight_sql_public_port must be a valid TCP port")
        if (
            self.flight_sql_fe_public_host is not None
            and not self.flight_sql_fe_public_host.strip()
        ):
            raise ValueError("flight_sql_fe_public_host must not be empty")
        if self.flight_sql_max_message_size < 1:
            raise ValueError("flight_sql_max_message_size must be positive")
        if self.flight_sql_query_timeout_seconds <= 0:
            raise ValueError("flight_sql_query_timeout_seconds must be positive")
        if self.flight_sql_fetch_timeout_seconds <= 0:
            raise ValueError("flight_sql_fetch_timeout_seconds must be positive")

    @classmethod
    def from_environment(cls) -> DorisConfig:
        defaults = cls()
        env = os.getenv
        table = env("DDON_DORIS_TABLE", defaults.table)
        variant = env("DDON_DORIS_SERVING_VARIANT_ID", defaults.serving_variant_id)
        (
            definition_lookup_table,
            name_lookup_table,
            method_lookup_table,
            die_lookup_table,
            statistics_policy,
            reference_prefetch,
            attribute_projection,
            child_tag_filter,
            hydration_scope,
        ) = _serving_environment_values(table, variant, defaults)
        return cls(
            http_url=env("DDON_DORIS_HTTP_URL", defaults.http_url),
            stream_load_url=env("DDON_DORIS_STREAM_LOAD_URL", defaults.stream_load_url),
            sql_host=env("DDON_DORIS_SQL_HOST", defaults.sql_host),
            sql_port=_positive_environment_int("DDON_DORIS_SQL_PORT", defaults.sql_port),
            database=env("DDON_DORIS_DATABASE", defaults.database),
            user=env("DDON_DORIS_USER", defaults.user),
            password=env("DDON_DORIS_PASSWORD", defaults.password),
            table=table,
            **flight_environment_values(defaults),
            definition_lookup_table=definition_lookup_table,
            name_lookup_table=name_lookup_table,
            method_lookup_table=method_lookup_table,
            die_lookup_table=die_lookup_table,
            analyze_after_load=_boolean_environment(
                "DDON_DORIS_ANALYZE_AFTER_LOAD", defaults.analyze_after_load
            ),
            analyze_wait_seconds=_nonnegative_environment_float(
                "DDON_DORIS_ANALYZE_WAIT_SECONDS", defaults.analyze_wait_seconds
            ),
            stream_load_workers=_positive_environment_int(
                "DDON_DORIS_STREAM_LOAD_WORKERS", defaults.stream_load_workers
            ),
            stream_load_connect_timeout_seconds=_positive_environment_float(
                "DDON_DORIS_STREAM_LOAD_CONNECT_TIMEOUT_SECONDS",
                defaults.stream_load_connect_timeout_seconds,
            ),
            stream_load_read_timeout_seconds=_positive_environment_float(
                "DDON_DORIS_STREAM_LOAD_READ_TIMEOUT_SECONDS",
                defaults.stream_load_read_timeout_seconds,
            ),
            stream_load_write_timeout_seconds=_positive_environment_float(
                "DDON_DORIS_STREAM_LOAD_WRITE_TIMEOUT_SECONDS",
                defaults.stream_load_write_timeout_seconds,
            ),
            **_sql_timeout_environment_values(defaults),
            publication_verify_timeout_seconds=_positive_environment_float(
                "DDON_DORIS_PUBLICATION_VERIFY_TIMEOUT_SECONDS",
                defaults.publication_verify_timeout_seconds,
            ),
            statistics_policy=statistics_policy,
            reference_prefetch=reference_prefetch,
            attribute_projection=attribute_projection,
            child_tag_filter=child_tag_filter,
            hydration_scope=hydration_scope,
            serving_variant_id=variant,
            query_trace=DorisQueryTraceConfig.from_environment(),
            capture_statistics_evidence=_boolean_environment(
                "DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE", defaults.capture_statistics_evidence
            ),
        )


def _sql_timeout_environment_values(defaults: DorisConfig) -> _SqlTimeoutEnvironmentValues:
    return {
        "sql_connect_timeout_seconds": _positive_environment_float(
            "DDON_DORIS_SQL_CONNECT_TIMEOUT_SECONDS", defaults.sql_connect_timeout_seconds
        ),
        "sql_read_timeout_seconds": _positive_environment_float(
            "DDON_DORIS_SQL_READ_TIMEOUT_SECONDS", defaults.sql_read_timeout_seconds
        ),
        "sql_write_timeout_seconds": _positive_environment_float(
            "DDON_DORIS_SQL_WRITE_TIMEOUT_SECONDS", defaults.sql_write_timeout_seconds
        ),
    }


def _serving_environment_values(
    table: str,
    variant: str,
    defaults: DorisConfig,
) -> tuple[str | None, str | None, str | None, str | None, str, str, str, str, str]:
    default_lookup = default_name_lookup_table(table)
    canonical = variant == "canonical"
    definition = _serving_environment_value(
        "DDON_DORIS_DEFINITION_LOOKUP_TABLE", default_lookup, canonical
    )
    name = _serving_environment_value("DDON_DORIS_NAME_LOOKUP_TABLE", default_lookup, canonical)
    return (
        None if definition == default_lookup else definition,
        None if name == default_lookup else name,
        _optional_serving_environment_value("DDON_DORIS_METHOD_LOOKUP_TABLE", canonical),
        _optional_serving_environment_value("DDON_DORIS_DIE_LOOKUP_TABLE", canonical),
        _serving_environment_value(
            "DDON_DORIS_STATISTICS_POLICY", defaults.statistics_policy, canonical
        ),
        _serving_environment_value(
            "DDON_DORIS_REFERENCE_PREFETCH", defaults.reference_prefetch, canonical
        ),
        _serving_environment_value(
            "DDON_DORIS_ATTRIBUTE_PROJECTION", defaults.attribute_projection, canonical
        ),
        _serving_environment_value(
            "DDON_DORIS_CHILD_TAG_FILTER", defaults.child_tag_filter, canonical
        ),
        _serving_environment_value(
            "DDON_DORIS_HYDRATION_SCOPE", defaults.hydration_scope, canonical
        ),
    )


def _boolean_environment(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean environment value for {name}: {value!r}")


def _serving_environment_value(name: str, default: str, canonical: bool) -> str:
    """Parse one serving policy without silently discarding canonical overrides."""
    value = os.getenv(name)
    if value is None:
        return default
    if canonical and value != default:
        raise ValueError(
            f"{name} cannot override canonical Doris serving policy; "
            "select an explicit non-canonical serving variant"
        )
    return value


def _optional_serving_environment_value(name: str, canonical: bool) -> str | None:
    """Parse optional physical lookup overrides without a canonical fallback."""
    value = os.getenv(name)
    if value is None:
        return None
    if canonical:
        raise ValueError(
            f"{name} cannot override canonical Doris serving policy; "
            "select an explicit non-canonical serving variant"
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _validate_stream_load_timeouts(config: DorisConfig) -> None:
    for field_name, timeout in (
        ("stream_load_connect_timeout_seconds", config.stream_load_connect_timeout_seconds),
        ("stream_load_read_timeout_seconds", config.stream_load_read_timeout_seconds),
        ("stream_load_write_timeout_seconds", config.stream_load_write_timeout_seconds),
    ):
        if timeout <= 0:
            raise ValueError(f"{field_name} must be positive")


def _validate_sql_timeouts(config: DorisConfig) -> None:
    for field_name, timeout in (
        ("sql_connect_timeout_seconds", config.sql_connect_timeout_seconds),
        ("sql_read_timeout_seconds", config.sql_read_timeout_seconds),
        ("sql_write_timeout_seconds", config.sql_write_timeout_seconds),
    ):
        if timeout <= 0:
            raise ValueError(f"{field_name} must be positive")


def _positive_environment_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"Invalid integer environment value for {name}: {value!r}") from error
    if parsed < 1:
        raise ValueError(f"Environment value for {name} must be positive: {value!r}")
    return parsed


def _nonnegative_environment_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid number environment value for {name}: {value!r}") from error
    if parsed < 0:
        raise ValueError(f"Environment value for {name} must not be negative: {value!r}")
    return parsed


def _positive_environment_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid number environment value for {name}: {value!r}") from error
    if parsed <= 0:
        raise ValueError(f"Environment value for {name} must be positive: {value!r}")
    return parsed

"""Doris table and bounded Parquet load plans."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from ...domain.models.analytical_dwarf import MaterializationManifest
from .doris_layout import _FAMILIES, _family_table, _identifier
from .doris_optimization import DorisQueryTraceConfig, DorisServingVariant
from .doris_registry import publish_registry, registry_sql
from .doris_schema import _FAMILY_COLUMNS
from .doris_statistics import analyze_tables, collect_statistics_evidence
from .doris_validation import (
    validate_manifest_for_load as _validate_manifest_for_load,
)
from .doris_validation import (
    validate_plan_files as _validate_plan_files,
)
from .doris_validation import (
    validate_plan_manifest_files as _validate_plan_manifest_files,
)
from .doris_validation import (
    validate_plan_settings as _validate_plan_settings,
)
from .manifest import (
    declared_parquet_files,
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
)
from .optional import import_optional


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
    reference_prefetch: str = "eager"
    attribute_projection: str = "full"
    child_tag_filter: str = "all"
    hydration_scope: str = "global"
    serving_variant_id: str = "canonical"
    query_trace: DorisQueryTraceConfig | None = None
    capture_statistics_evidence: bool = False

    def __post_init__(self) -> None:
        if self.analyze_wait_seconds < 0:
            raise ValueError("analyze_wait_seconds must not be negative")
        if self.stream_load_workers < 1:
            raise ValueError("stream_load_workers must be positive")
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
        return cls(
            http_url=os.getenv("DDON_DORIS_HTTP_URL", defaults.http_url),
            stream_load_url=os.getenv("DDON_DORIS_STREAM_LOAD_URL", defaults.stream_load_url),
            sql_host=os.getenv("DDON_DORIS_SQL_HOST", defaults.sql_host),
            sql_port=int(os.getenv("DDON_DORIS_SQL_PORT", str(defaults.sql_port))),
            database=os.getenv("DDON_DORIS_DATABASE", defaults.database),
            user=os.getenv("DDON_DORIS_USER", defaults.user),
            password=os.getenv("DDON_DORIS_PASSWORD", defaults.password),
            table=os.getenv("DDON_DORIS_TABLE", defaults.table),
            definition_lookup_table=env(
                "DDON_DORIS_DEFINITION_LOOKUP_TABLE", defaults.definition_lookup_table
            ),
            name_lookup_table=os.getenv("DDON_DORIS_NAME_LOOKUP_TABLE", defaults.name_lookup_table),
            method_lookup_table=env("DDON_DORIS_METHOD_LOOKUP_TABLE", defaults.method_lookup_table),
            die_lookup_table=env("DDON_DORIS_DIE_LOOKUP_TABLE", defaults.die_lookup_table),
            flight_sql_host=os.getenv("DDON_DORIS_FLIGHT_SQL_HOST", defaults.flight_sql_host),
            flight_sql_port=int(
                os.getenv("DDON_DORIS_FLIGHT_SQL_PORT", str(defaults.flight_sql_port))
            ),
            flight_sql_uri=os.getenv("DDON_DORIS_FLIGHT_SQL_URI", defaults.flight_sql_uri),
            flight_sql_fe_public_host=os.getenv(
                "DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST", defaults.flight_sql_fe_public_host
            ),
            flight_sql_public_host=os.getenv(
                "DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST", defaults.flight_sql_public_host
            ),
            flight_sql_public_port=int(
                os.getenv("DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT", str(defaults.flight_sql_public_port))
            ),
            flight_sql_max_message_size=int(
                os.getenv(
                    "DDON_DORIS_FLIGHT_SQL_MAX_MESSAGE_SIZE",
                    str(defaults.flight_sql_max_message_size),
                )
            ),
            flight_sql_query_timeout_seconds=float(
                os.getenv(
                    "DDON_DORIS_FLIGHT_SQL_QUERY_TIMEOUT_SECONDS",
                    str(defaults.flight_sql_query_timeout_seconds),
                )
            ),
            flight_sql_fetch_timeout_seconds=float(
                os.getenv(
                    "DDON_DORIS_FLIGHT_SQL_FETCH_TIMEOUT_SECONDS",
                    str(defaults.flight_sql_fetch_timeout_seconds),
                )
            ),
            analyze_after_load=_boolean_environment(
                "DDON_DORIS_ANALYZE_AFTER_LOAD", defaults.analyze_after_load
            ),
            analyze_wait_seconds=_nonnegative_environment_float(
                "DDON_DORIS_ANALYZE_WAIT_SECONDS", defaults.analyze_wait_seconds
            ),
            stream_load_workers=_positive_environment_int(
                "DDON_DORIS_STREAM_LOAD_WORKERS", defaults.stream_load_workers
            ),
            statistics_policy=os.getenv("DDON_DORIS_STATISTICS_POLICY", defaults.statistics_policy),
            reference_prefetch=os.getenv(
                "DDON_DORIS_REFERENCE_PREFETCH", defaults.reference_prefetch
            ),
            attribute_projection=os.getenv(
                "DDON_DORIS_ATTRIBUTE_PROJECTION", defaults.attribute_projection
            ),
            child_tag_filter=os.getenv("DDON_DORIS_CHILD_TAG_FILTER", defaults.child_tag_filter),
            hydration_scope=os.getenv("DDON_DORIS_HYDRATION_SCOPE", defaults.hydration_scope),
            serving_variant_id=env("DDON_DORIS_SERVING_VARIANT_ID", defaults.serving_variant_id),
            query_trace=DorisQueryTraceConfig.from_environment(),
            capture_statistics_evidence=_boolean_environment(
                "DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE", defaults.capture_statistics_evidence
            ),
        )


@dataclass(frozen=True, slots=True)
class DorisLoadPlan:
    """Deterministic SQL and file plan for one store."""

    database: str
    table: str
    sql: tuple[str, ...]
    parquet_files: tuple[Path, ...]
    manifest_path: Path
    definition_lookup_table: str | None = None
    name_lookup_table: str | None = None
    method_lookup_table: str | None = None
    die_lookup_table: str | None = None
    analyze_after_load: bool = False
    analyze_wait_seconds: float = 0.0
    stream_load_workers: int = 1
    statistics_policy: str = "selective"
    serving_variant_id: str = "canonical"
    capture_statistics_evidence: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "database": self.database,
            "table": self.table,
            "sql": list(self.sql),
            "parquet_files": [str(path) for path in self.parquet_files],
            "manifest_path": str(self.manifest_path),
            "table_families": list(_FAMILIES),
            "definition_lookup_table": self.definition_lookup_table,
            "name_lookup_table": self.name_lookup_table,
            "method_lookup_table": self.method_lookup_table,
            "die_lookup_table": self.die_lookup_table,
            "analyze_after_load": self.analyze_after_load,
            "analyze_wait_seconds": self.analyze_wait_seconds,
            "stream_load_workers": self.stream_load_workers,
            "statistics_policy": self.statistics_policy,
            "serving_variant_id": self.serving_variant_id,
            "capture_statistics_evidence": self.capture_statistics_evidence,
        }


def build_doris_plan(
    manifest_path: Path,
    config: DorisConfig | None = None,
) -> DorisLoadPlan:
    """Build the native Doris DDL and Parquet load plan without contacting Doris."""
    config = config or DorisConfig.from_environment()
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if manifest.status != "complete":
        raise ValueError(f"Doris loading requires a complete analytical store: {manifest_path}")
    if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
        raise ValueError(f"Doris loading requires complete DWARF parsing: {manifest_path}")
    parquet_files = declared_parquet_files(manifest_path, manifest)
    return DorisLoadPlan(
        config.database,
        config.table,
        tuple(_native_sql(config)),
        parquet_files,
        manifest_path,
        config.definition_lookup_table,
        config.name_lookup_table,
        config.method_lookup_table,
        config.die_lookup_table,
        config.analyze_after_load,
        config.analyze_wait_seconds,
        config.stream_load_workers,
        config.statistics_policy,
        config.serving_variant_id,
        config.capture_statistics_evidence,
    )


class DorisLoader:
    """Execute a precomputed plan through SQL and streaming Parquet uploads."""

    def execute(self, plan: DorisLoadPlan, config: DorisConfig | None = None) -> dict[str, object]:
        config = config or DorisConfig.from_environment()
        self._validate_plan(plan, config)
        pymysql = import_optional("pymysql", "analytical")
        connection = pymysql.connect(
            host=config.sql_host,
            port=config.sql_port,
            user=config.user,
            password=config.password,
            autocommit=True,
        )
        try:
            self._execute_sql(connection, plan)
            loaded = self._load_native_files(plan, config)
            analysis = analyze_tables(connection, plan, config)
            manifest = _load_manifest(plan.manifest_path)
            serving_variant = DorisServingVariant.from_config(
                config,
                source_id=getattr(getattr(manifest, "source_identity", None), "sha256", None),
                schema_version=getattr(manifest, "schema_version", None),
            )
            registry = publish_registry(
                connection,
                config.database,
                config.table,
                plan.manifest_path,
                manifest,
                serving_variant_id=config.serving_variant_id,
                serving_variant_configuration_sha256=serving_variant.configuration_sha256,
            )
            result: dict[str, object] = {
                "status": "observed",
                "plan": plan.to_dict(),
                "loads": loaded,
                "analysis": analysis,
                "statistics_evidence": (
                    collect_statistics_evidence(connection, plan)
                    if config.capture_statistics_evidence
                    else {"status": "not_observed", "reason": "capture disabled"}
                ),
                "registry": {
                    "source_id": registry.source_id,
                    "status": registry.status,
                    "expected_counts": registry.expected_counts,
                    "observed_counts": registry.observed_counts,
                    "serving_variant_id": getattr(registry, "serving_variant_id", None),
                    "serving_variant_configuration_sha256": getattr(
                        registry, "serving_variant_configuration_sha256", None
                    ),
                },
            }
            return result
        finally:
            connection.close()

    @staticmethod
    def _validate_plan(plan: DorisLoadPlan, config: DorisConfig) -> None:
        manifest_path = plan.manifest_path.resolve()
        manifest = load_manifest(manifest_path)
        _validate_manifest_for_load(manifest, manifest_path)
        _validate_plan_files(plan, manifest_path, manifest)
        _validate_plan_settings(plan, config)
        _validate_plan_manifest_files(manifest_path, manifest)

    @staticmethod
    def _execute_sql(connection: Any, plan: DorisLoadPlan) -> list[dict[str, object]]:
        with connection.cursor() as cursor:
            for statement in plan.sql:
                cursor.execute(statement)
        return []

    def _load_native_files(
        self, plan: DorisLoadPlan, config: DorisConfig
    ) -> list[dict[str, object]]:
        def load_file(parquet_file: Path) -> dict[str, object]:
            family = _family_for_file(parquet_file, plan.manifest_path)
            return self._stream_load(
                parquet_file,
                config,
                _family_table(plan.table, family),
                _load_label(plan, family, parquet_file),
            )

        if config.stream_load_workers == 1 or len(plan.parquet_files) < 2:
            return [load_file(parquet_file) for parquet_file in plan.parquet_files]
        with ThreadPoolExecutor(max_workers=config.stream_load_workers) as executor:
            # executor.map preserves the plan's deterministic file order while
            # allowing independent labeled Stream Loads to overlap network and
            # FE/BE transaction latency.
            return list(executor.map(load_file, plan.parquet_files))

    @staticmethod
    def _stream_load(
        path: Path,
        config: DorisConfig,
        table: str,
        label: str,
    ) -> dict[str, object]:
        connection, response = DorisLoader._send_stream_load(
            path, config, table, config.stream_load_url, label
        )
        try:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.read()
                if not location:
                    raise RuntimeError(
                        "Doris Stream Load redirect did not include a Location header"
                    )
                connection.close()
                connection, response = DorisLoader._send_stream_load(
                    path, config, table, urljoin(config.http_url, location), label
                )
            body = response.read().decode("utf-8", errors="replace")
            if response.status >= 300:
                raise RuntimeError(
                    f"Doris Stream Load failed for {path}: HTTP {response.status}: {body[:500]}"
                )
            payload = json.loads(body)
            load_status = payload.get("Status")
            if load_status not in {"Success", "Publish Timeout"}:
                raise RuntimeError(
                    f"Doris Stream Load rejected {path}: {load_status}: {payload.get('Message', '')}"
                )
            return {"path": str(path), "status": response.status, "response": payload}
        finally:
            connection.close()

    @staticmethod
    def _send_stream_load(
        path: Path,
        config: DorisConfig,
        table: str,
        endpoint: str,
        label: str,
    ) -> tuple[Any, Any]:
        parsed = urlparse(endpoint)
        connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_type(parsed.hostname or "127.0.0.1", parsed.port)
        request_path = parsed.path or f"/api/{config.database}/{table}/_stream_load"
        if parsed.query:
            request_path = f"{request_path}?{parsed.query}"
        credentials = base64.b64encode(f"{config.user}:{config.password}".encode()).decode()
        connection.putrequest("PUT", request_path)
        connection.putheader("Authorization", f"Basic {credentials}")
        connection.putheader("format", "parquet")
        connection.putheader("label", label)
        connection.putheader("strict_mode", "true")
        connection.putheader("max_filter_ratio", "0")
        connection.putheader("Content-Length", str(path.stat().st_size))
        connection.putheader("Expect", "100-continue")
        connection.endheaders()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                connection.send(chunk)
        return connection, connection.getresponse()


def _native_sql(config: DorisConfig) -> list[str]:
    database = _identifier(config.database)
    statements = [f"CREATE DATABASE IF NOT EXISTS {database}"]
    for family in _FAMILIES:
        table = _identifier(_family_table(config.table, family))
        columns = ",\n    ".join(_native_columns(family))
        keys = ", ".join(_FAMILY_KEYS[family])
        bloom = ",".join(_FAMILY_BLOOM_COLUMNS[family])
        distribution = _FAMILY_DISTRIBUTION[family]
        statements.append(
            f"""CREATE TABLE IF NOT EXISTS {database}.{table} (
    {columns}
) ENGINE=OLAP
DUPLICATE KEY({keys})
DISTRIBUTED BY {distribution}
PROPERTIES ("replication_num" = "1", "compression" = "zstd", "bloom_filter_columns" = "{bloom}")"""
        )
    statements.append(registry_sql(config.database, config.table))
    statements.append(
        f"ALTER TABLE {database}.{_identifier(_family_table(config.table, 'index'))} "
        "ADD INDEX IF NOT EXISTS idx_name (name) USING INVERTED"
    )
    statements.append(
        f"ALTER TABLE {database}.{_identifier(_family_table(config.table, 'attribute'))} "
        "ADD INDEX IF NOT EXISTS idx_attribute_name (name) USING INVERTED"
    )
    statements.append(
        f"ALTER TABLE {database}.{_identifier(_family_table(config.table, 'name'))} "
        "ADD INDEX IF NOT EXISTS idx_name_value (name) USING INVERTED"
    )
    return statements


def _native_columns(family: str) -> tuple[str, ...]:
    """Place every duplicate-key column at the required schema prefix."""
    definitions = _FAMILY_COLUMNS[family]
    by_name = {_column_name(definition): definition for definition in definitions}
    keys = _FAMILY_KEYS[family]
    missing = tuple(key for key in keys if key not in by_name)
    if missing:
        raise ValueError(f"Doris key columns missing from {family} schema: {missing}")
    key_definitions = tuple(by_name[key] for key in keys)
    key_names = set(keys)
    remaining = tuple(
        definition for definition in definitions if _column_name(definition) not in key_names
    )
    return key_definitions + remaining


def _column_name(definition: str) -> str:
    """Extract a Doris column identifier from a column definition."""
    return definition.split(maxsplit=1)[0].strip("`")


def _load_manifest(path: Path) -> MaterializationManifest:
    from .manifest import load_manifest

    return load_manifest(path)


_FAMILY_KEYS = {
    "section": ("source_id", "section_index"),
    "raw_chunk": ("source_id", "section_index", "chunk_index"),
    "unit": ("source_id", "unit_offset"),
    "die": ("source_id", "unit_offset", "die_offset", "ordinal"),
    "attribute": ("source_id", "unit_offset", "die_offset", "ordinal"),
    "reference": ("source_id", "unit_offset", "die_offset", "attribute_name", "relation"),
    "index": ("source_id", "unit_offset", "die_offset", "index_type"),
    "range": ("source_id", "unit_offset", "die_offset", "ordinal"),
    "location": ("source_id", "unit_offset", "die_offset", "ordinal"),
    "line": ("source_id", "unit_offset", "ordinal"),
    "macro": ("source_id", "section_name", "record_offset"),
    "frame": ("source_id", "section_name", "record_offset"),
    "abbreviation": ("source_id", "unit_offset", "abbrev_code"),
    "name": ("source_id", "unit_offset", "die_offset", "ordinal"),
}

_FAMILY_BLOOM_COLUMNS = {
    "section": ("source_id", "section_index"),
    "raw_chunk": ("source_id", "section_index", "chunk_index"),
    "unit": ("source_id", "unit_offset"),
    "die": ("source_id", "unit_offset", "die_offset", "parent_offset"),
    "attribute": ("source_id", "unit_offset", "die_offset", "name"),
    "reference": ("source_id", "unit_offset", "die_offset", "target_offset"),
    "index": ("source_id", "unit_offset", "die_offset", "target_offset", "name"),
    "range": ("source_id", "unit_offset", "die_offset", "start_address", "end_address"),
    "location": ("source_id", "unit_offset", "die_offset", "start_address", "end_address"),
    "line": ("source_id", "unit_offset", "address", "file_index"),
    "macro": ("source_id", "section_name", "record_offset"),
    "frame": ("source_id", "section_name", "record_offset"),
    "abbreviation": ("source_id", "unit_offset", "abbrev_code"),
    "name": ("source_id", "unit_offset", "die_offset", "name"),
}

_FAMILY_DISTRIBUTION = {
    "section": "HASH(source_id, section_index) BUCKETS 3",
    "raw_chunk": "HASH(source_id, section_index) BUCKETS 3",
    "unit": "HASH(source_id, unit_offset) BUCKETS 8",
    "die": "HASH(source_id, unit_offset) BUCKETS 16",
    "attribute": "HASH(source_id, unit_offset) BUCKETS 16",
    "reference": "HASH(source_id, unit_offset) BUCKETS 16",
    "index": "HASH(source_id, unit_offset) BUCKETS 8",
    "range": "HASH(source_id, unit_offset) BUCKETS 16",
    "location": "HASH(source_id, unit_offset) BUCKETS 16",
    "line": "HASH(source_id, unit_offset) BUCKETS 16",
    "macro": "HASH(source_id, section_name) BUCKETS 3",
    "frame": "HASH(source_id, section_name) BUCKETS 3",
    "abbreviation": "HASH(source_id, unit_offset) BUCKETS 8",
    "name": "HASH(source_id, unit_offset) BUCKETS 16",
}


def _family_for_file(path: Path, manifest_path: Path) -> str:
    parquet_root = manifest_path.resolve().parent / "parquet"
    relative = path.resolve().relative_to(parquet_root)
    family = relative.parts[0]
    if family not in _FAMILIES:
        raise ValueError(f"Parquet file is not under a supported family directory: {path}")
    return family


def _load_label(plan: DorisLoadPlan, family: str, path: Path) -> str:
    """Return a repeatable label so a manifest cannot silently duplicate rows."""
    source = _load_manifest(plan.manifest_path).source_identity.sha256[:16]
    root = plan.manifest_path.resolve().parent
    relative = path.resolve().relative_to(root).as_posix()
    path_key = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    return f"ddon_{source}_{family}_{path_key}"


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

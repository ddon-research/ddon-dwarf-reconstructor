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
from .doris_config_environment import flight_environment_values
from .doris_ddl import (
    _FAMILY_BLOOM_COLUMNS,
    _FAMILY_DISTRIBUTION,
    _FAMILY_KEYS,
    _native_columns,
    _native_sql,
)
from .doris_layout import _FAMILIES, _family_table, _identifier, default_name_lookup_table
from .doris_optimization import DorisQueryTraceConfig, DorisServingVariant
from .doris_registry import publish_registry
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

__all__ = [
    "DorisConfig",
    "DorisLoadPlan",
    "DorisLoader",
    "_FAMILY_BLOOM_COLUMNS",
    "_FAMILY_DISTRIBUTION",
    "_FAMILY_KEYS",
    "_native_columns",
    "_native_sql",
    "build_doris_plan",
]


def _load_manifest(path: Path) -> MaterializationManifest:
    """Load a materialization manifest for planning and repeatable load labels."""
    return load_manifest(path)


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
        serving_variant_id = env("DDON_DORIS_SERVING_VARIANT_ID", defaults.serving_variant_id)
        canonical_serving = serving_variant_id == "canonical"
        return cls(
            http_url=os.getenv("DDON_DORIS_HTTP_URL", defaults.http_url),
            stream_load_url=os.getenv("DDON_DORIS_STREAM_LOAD_URL", defaults.stream_load_url),
            sql_host=os.getenv("DDON_DORIS_SQL_HOST", defaults.sql_host),
            sql_port=int(os.getenv("DDON_DORIS_SQL_PORT", str(defaults.sql_port))),
            database=os.getenv("DDON_DORIS_DATABASE", defaults.database),
            user=os.getenv("DDON_DORIS_USER", defaults.user),
            password=os.getenv("DDON_DORIS_PASSWORD", defaults.password),
            table=os.getenv("DDON_DORIS_TABLE", defaults.table),
            **flight_environment_values(defaults),
            definition_lookup_table=(
                defaults.definition_lookup_table
                if canonical_serving
                else env("DDON_DORIS_DEFINITION_LOOKUP_TABLE", defaults.definition_lookup_table)
            ),
            name_lookup_table=(
                defaults.name_lookup_table
                if canonical_serving
                else env("DDON_DORIS_NAME_LOOKUP_TABLE", defaults.name_lookup_table)
            ),
            method_lookup_table=env("DDON_DORIS_METHOD_LOOKUP_TABLE", defaults.method_lookup_table),
            die_lookup_table=env("DDON_DORIS_DIE_LOOKUP_TABLE", defaults.die_lookup_table),
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
            reference_prefetch=(
                defaults.reference_prefetch
                if canonical_serving
                else env("DDON_DORIS_REFERENCE_PREFETCH", defaults.reference_prefetch)
            ),
            attribute_projection=(
                defaults.attribute_projection
                if canonical_serving
                else env("DDON_DORIS_ATTRIBUTE_PROJECTION", defaults.attribute_projection)
            ),
            child_tag_filter=os.getenv("DDON_DORIS_CHILD_TAG_FILTER", defaults.child_tag_filter),
            hydration_scope=os.getenv("DDON_DORIS_HYDRATION_SCOPE", defaults.hydration_scope),
            serving_variant_id=serving_variant_id,
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
            "definition_lookup_table": self.effective_definition_lookup_table,
            "name_lookup_table": self.effective_name_lookup_table,
            "method_lookup_table": self.method_lookup_table,
            "die_lookup_table": self.die_lookup_table,
            "analyze_after_load": self.analyze_after_load,
            "analyze_wait_seconds": self.analyze_wait_seconds,
            "stream_load_workers": self.stream_load_workers,
            "statistics_policy": self.statistics_policy,
            "serving_variant_id": self.serving_variant_id,
            "capture_statistics_evidence": self.capture_statistics_evidence,
        }

    @property
    def effective_definition_lookup_table(self) -> str:
        """Return the source/name table used for definition lookup."""
        return self.definition_lookup_table or default_name_lookup_table(self.table)

    @property
    def effective_name_lookup_table(self) -> str:
        """Return the source/name table used for name lookup."""
        return self.name_lookup_table or default_name_lookup_table(self.table)


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
        config.effective_definition_lookup_table,
        config.effective_name_lookup_table,
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
            manifest = _load_manifest(plan.manifest_path)
            lookup_load = self._populate_promoted_name_lookup(
                connection,
                plan,
                config,
                manifest.source_identity.sha256,
            )
            analysis = analyze_tables(connection, plan, config)
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
                "lookup_load": lookup_load,
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

    @staticmethod
    def _populate_promoted_name_lookup(
        connection: Any,
        plan: DorisLoadPlan,
        config: DorisConfig,
        source_id: str,
    ) -> dict[str, object]:
        if not config.uses_promoted_name_lookup:
            return {
                "status": "not_applicable",
                "reason": "non-canonical serving variant owns its lookup table",
            }
        database = _identifier(config.database)
        lookup_table = _identifier(config.effective_name_lookup_table)
        source_table = _identifier(_family_table(plan.table, "index"))
        delete = f"DELETE FROM {database}.{lookup_table} WHERE source_id = %s"
        insert = (
            f"INSERT INTO {database}.{lookup_table} "
            "(source_id, name, unit_offset, die_offset, index_type, tag, target_offset, "
            "resolution_status) "
            f"SELECT source_id, name, unit_offset, die_offset, index_type, tag, target_offset, "
            f"resolution_status FROM {database}.{source_table} "
            "WHERE source_id = %s AND index_type = 'definition'"
        )
        count = f"SELECT COUNT(*) FROM {database}.{lookup_table} WHERE source_id = %s"
        with connection.cursor() as cursor:
            cursor.execute(delete, (source_id,))
            cursor.execute(insert, (source_id,))
            cursor.execute(count, (source_id,))
            rows = cursor.fetchall()
        row_count = int(rows[0][0]) if rows else 0
        return {
            "status": "observed",
            "table": config.effective_name_lookup_table,
            "source_id": source_id,
            "row_count": row_count,
            "delete_sql": delete,
            "insert_sql": insert,
        }

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

"""Doris table and bounded Parquet load plans."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import MaterializationManifest
from .doris_config import DorisConfig
from .doris_ddl import (
    _FAMILY_BLOOM_COLUMNS,
    _FAMILY_DISTRIBUTION,
    _FAMILY_KEYS,
    _native_columns,
    _native_sql,
)
from .doris_layout import _FAMILIES, _family_table, _identifier, default_name_lookup_table
from .doris_publication import DorisPublicationVerifier
from .doris_registry import migrate_registry_schema, publish_registry
from .doris_serving_profile import DorisServingProfile
from .doris_statistics import analyze_tables, collect_statistics_evidence
from .doris_stream_load import DorisStreamLoadClient, StreamLoadState
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
            connect_timeout=config.sql_connect_timeout_seconds,
            read_timeout=config.sql_read_timeout_seconds,
            write_timeout=config.sql_write_timeout_seconds,
        )
        try:
            self._execute_sql(connection, plan)
            migrate_registry_schema(connection, config.database, config.table)
            loaded = self._load_native_files(plan, config)
            return self._complete_load(connection, plan, config, loaded)
        finally:
            connection.close()

    def _complete_load(
        self,
        connection: Any,
        plan: DorisLoadPlan,
        config: DorisConfig,
        loaded: list[dict[str, object]],
    ) -> dict[str, object]:
        manifest = _load_manifest(plan.manifest_path)
        pending_loads = tuple(
            load for load in loaded if str(load.get("status")) == "publish_pending"
        )
        publication_verification = self._verify_pending_publication(
            connection, plan, config, manifest, bool(pending_loads)
        )
        if publication_verification["status"] != "not_observed" and not bool(
            publication_verification.get("row_count_verified")
        ):
            return self._incomplete_load_result(plan, loaded, publication_verification)
        lookup_load = self._populate_promoted_name_lookup(
            connection, plan, config, manifest.source_identity.sha256
        )
        analysis = analyze_tables(connection, plan, config)
        serving_variant = DorisServingProfile.from_config(
            config,
            source_id=manifest.source_identity.sha256,
            schema_version=manifest.schema_version,
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
        return {
            "status": "observed",
            "plan": plan.to_dict(),
            "loads": loaded,
            "load_status": ("publish_pending_verified" if pending_loads else "loaded"),
            "load_states": tuple(str(load.get("status", "unknown")) for load in loaded),
            "publication_verification": {
                **publication_verification,
                "pending_load_count": len(pending_loads),
                "registry_status": registry.status,
            },
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
                "serving_variant_id": registry.serving_variant_id,
                "serving_variant_configuration_sha256": registry.serving_variant_configuration_sha256,
            },
        }

    @staticmethod
    def _verify_pending_publication(
        connection: Any,
        plan: DorisLoadPlan,
        config: DorisConfig,
        manifest: MaterializationManifest,
        has_pending_loads: bool,
    ) -> dict[str, object]:
        if not has_pending_loads:
            return {
                "status": "observed",
                "row_count_verified": True,
                "verification_scope": "registry_reconciliation",
                "reason": "stream loads reported terminal outcomes",
            }
        verification = DorisPublicationVerifier(config.publication_verify_timeout_seconds).verify(
            connection,
            config.database,
            plan.table,
            manifest.source_identity.sha256,
            {family: manifest.counts.get(family, 0) for family in _FAMILIES},
        )
        return verification.to_dict()

    @staticmethod
    def _incomplete_load_result(
        plan: DorisLoadPlan,
        loaded: list[dict[str, object]],
        publication_verification: dict[str, object],
    ) -> dict[str, object]:
        """Return explicit partial evidence without publishing a stale registry row."""
        return {
            "status": "partial",
            "plan": plan.to_dict(),
            "loads": loaded,
            "load_status": "publish_pending",
            "load_states": tuple(str(load.get("status", "unknown")) for load in loaded),
            "publication_verification": publication_verification,
            "lookup_load": {
                "status": "not_observed",
                "reason": "lookup publication waits for complete row-count parity",
            },
            "analysis": {"status": "not_observed", "reason": "load publication incomplete"},
            "statistics_evidence": {
                "status": "not_observed",
                "reason": "load publication incomplete",
            },
            "registry": {"status": "not_observed", "reason": "load publication incomplete"},
        }

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
        source_count = (
            f"SELECT COUNT(*) FROM {database}.{source_table} "
            "WHERE source_id = %s AND index_type = 'definition'"
        )
        insert = (
            f"INSERT INTO {database}.{lookup_table} "
            "(source_id, name, unit_offset, die_offset, index_type, tag, target_offset, "
            "resolution_status) "
            f"SELECT source_id, name, unit_offset, die_offset, index_type, tag, target_offset, "
            f"resolution_status FROM {database}.{source_table} "
            "WHERE source_id = %s AND index_type = 'definition'"
        )
        count = (
            f"SELECT COUNT(*) FROM {database}.{lookup_table} "
            "WHERE source_id = %s AND index_type = 'definition'"
        )
        with connection.cursor() as cursor:
            cursor.execute(source_count, (source_id,))
            source_rows = cursor.fetchall()
            expected_count = int(source_rows[0][0]) if source_rows else 0
            cursor.execute(count, (source_id,))
            existing_rows = cursor.fetchall()
            existing_count = int(existing_rows[0][0]) if existing_rows else 0
            if existing_count:
                if existing_count != expected_count:
                    raise RuntimeError(
                        "Doris promoted name lookup is already populated with an "
                        "incomplete or stale source; refusing an append-only repair: "
                        f"expected={expected_count}, existing={existing_count}"
                    )
                return {
                    "status": "observed",
                    "table": config.effective_name_lookup_table,
                    "source_id": source_id,
                    "row_count": existing_count,
                    "expected_row_count": expected_count,
                    "publication": "reused_verified_count",
                }
            cursor.execute(insert, (source_id,))
            cursor.execute(count, (source_id,))
            rows = cursor.fetchall()
        row_count = int(rows[0][0]) if rows else 0
        if row_count != expected_count:
            raise RuntimeError(
                "Doris promoted name lookup reconciliation failed: "
                f"expected={expected_count}, observed={row_count}"
            )
        return {
            "status": "observed",
            "table": config.effective_name_lookup_table,
            "source_id": source_id,
            "row_count": row_count,
            "expected_row_count": expected_count,
            "insert_sql": insert,
            "publication": "inserted_and_verified",
        }

    def _load_native_files(
        self, plan: DorisLoadPlan, config: DorisConfig
    ) -> list[dict[str, object]]:
        client = DorisStreamLoadClient(config)

        def load_file(parquet_file: Path) -> dict[str, object]:
            family = _family_for_file(parquet_file, plan.manifest_path)
            outcome = client.load(
                parquet_file,
                _family_table(plan.table, family),
                _load_label(plan, family, parquet_file),
            )
            return outcome.to_dict()

        if config.stream_load_workers == 1 or len(plan.parquet_files) < 2:
            return self._validate_load_outcomes(
                [load_file(parquet_file) for parquet_file in plan.parquet_files]
            )
        with ThreadPoolExecutor(max_workers=config.stream_load_workers) as executor:
            # executor.map preserves the plan's deterministic file order while
            # allowing independent labeled Stream Loads to overlap network and
            # FE/BE transaction latency.
            futures = [executor.submit(load_file, path) for path in plan.parquet_files]
            results: list[dict[str, object]] = []
            failures: list[tuple[Path, Exception]] = []
            for path, future in zip(plan.parquet_files, futures, strict=True):
                try:
                    results.append(future.result())
                except Exception as error:
                    failures.append((path, error))
            if failures:
                detail = "; ".join(f"{path}: {error}" for path, error in failures[:5])
                raise RuntimeError(f"Doris Stream Load batch failed: {detail}") from failures[0][1]
            return self._validate_load_outcomes(results)

    @staticmethod
    def _validate_load_outcomes(results: list[dict[str, object]]) -> list[dict[str, object]]:
        failed = [
            result for result in results if result.get("status") == StreamLoadState.FAILED.value
        ]
        if failed:
            detail = "; ".join(
                f"{result.get('path')}: {result.get('diagnostics', 'unknown failure')}"
                for result in failed[:5]
            )
            raise RuntimeError(f"Doris Stream Load batch failed: {detail}")
        return results


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

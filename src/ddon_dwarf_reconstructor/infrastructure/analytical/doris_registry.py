"""Publication registry for complete source-bound Doris projections."""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import MaterializationManifest
from .doris_layout import _FAMILIES, _family_table, _identifier

REGISTRY_SCHEMA_VERSION = "2"


@dataclass(frozen=True, slots=True)
class DorisRegistrySnapshot:
    """Validated serving-projection publication metadata."""

    source_id: str
    schema_version: str
    status: str
    expected_counts: dict[str, int]
    observed_counts: dict[str, int]
    serving_variant_id: str | None = None
    serving_variant_configuration_sha256: str | None = None


def registry_table(base: str) -> str:
    """Return the registry table name for a Doris table family prefix."""
    return f"{base}_registry"


def registry_sql(database: str, base: str) -> str:
    """Build the idempotent registry table DDL."""
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    return f"""CREATE TABLE IF NOT EXISTS {table} (
    source_id CHAR(64) NOT NULL,
    schema_version VARCHAR(32) NOT NULL,
    source_path STRING,
    manifest_path STRING,
    expected_counts_json STRING,
    observed_counts_json STRING,
    status VARCHAR(32) NOT NULL,
    serving_variant_id VARCHAR(128),
    serving_variant_configuration_sha256 CHAR(64),
    registry_schema_version VARCHAR(16) NOT NULL,
    published_at DATETIME
) ENGINE=OLAP
DUPLICATE KEY(source_id)
DISTRIBUTED BY HASH(source_id) BUCKETS 3
PROPERTIES ("replication_num" = "1", "compression" = "zstd")"""


def registry_migration_sql(
    database: str,
    base: str,
    *,
    existing_columns: Collection[str] | None = None,
) -> tuple[str, ...]:
    """Return explicit DDL for missing columns in an older registry table.

    Existing rows are deliberately marked as legacy.  They cannot be trusted
    as a current publication until a complete load republishes the row with
    the current schema version and serving identity.  Doris does not support
    ``ADD COLUMN IF NOT EXISTS``, so callers must supply the observed columns
    when they need an idempotent migration.
    """
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    declarations = (
        ("serving_variant_id", "VARCHAR(128)"),
        ("serving_variant_configuration_sha256", "CHAR(64)"),
        ("registry_schema_version", "VARCHAR(16) DEFAULT 'legacy'"),
    )
    return tuple(
        f"ALTER TABLE {table} ADD COLUMN {name} {declaration}"
        for name, declaration in declarations
        if existing_columns is None or name not in existing_columns
    )


def migrate_registry_schema(connection: Any, database: str, base: str) -> None:
    """Apply the explicit registry schema migration before loading data."""
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    with connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = {str(row[0]) for row in cursor.fetchall()}
        for statement in registry_migration_sql(
            database,
            base,
            existing_columns=columns,
        ):
            cursor.execute(statement)


def publish_registry(
    connection: Any,
    database: str,
    base: str,
    manifest_path: Path,
    manifest: MaterializationManifest,
    *,
    serving_variant_id: str | None = None,
    serving_variant_configuration_sha256: str | None = None,
) -> DorisRegistrySnapshot:
    """Count every source family and publish only a complete reconciliation."""
    expected = _expected_counts(manifest)
    observed = _observed_counts(connection, database, base, manifest.source_identity.sha256)
    if observed != expected:
        raise ValueError(
            f"Doris serving projection count mismatch: expected={expected!r}, observed={observed!r}"
        )
    source_id = manifest.source_identity.sha256
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    payload = (
        source_id,
        manifest.schema_version,
        manifest.source_path,
        str(manifest_path.resolve()),
        json.dumps(expected, sort_keys=True, separators=(",", ":")),
        json.dumps(observed, sort_keys=True, separators=(",", ":")),
        "complete",
        REGISTRY_SCHEMA_VERSION,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} (source_id, schema_version, source_path, manifest_path, "
            "expected_counts_json, observed_counts_json, status, serving_variant_id, "
            "serving_variant_configuration_sha256, registry_schema_version, published_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())",
            (*payload[:7], serving_variant_id, serving_variant_configuration_sha256, payload[7]),
        )
        # Publish the replacement before retiring a legacy row.  If the
        # cleanup is interrupted, validation still fails closed on the legacy
        # row instead of observing an empty registry after a delete-first gap.
        cursor.execute(
            f"DELETE FROM {table} WHERE source_id = %s AND registry_schema_version <> %s",
            (source_id, REGISTRY_SCHEMA_VERSION),
        )
        cursor.execute(
            f"DELETE FROM {table} WHERE source_id = %s AND registry_schema_version IS NULL",
            (source_id,),
        )
        cursor.execute(
            f"DELETE FROM {table} WHERE source_id = %s AND registry_schema_version = %s "
            "AND manifest_path <> %s",
            (source_id, REGISTRY_SCHEMA_VERSION, str(manifest_path.resolve())),
        )
    return DorisRegistrySnapshot(
        source_id,
        manifest.schema_version,
        "complete",
        expected,
        observed,
        serving_variant_id,
        serving_variant_configuration_sha256,
    )


def validate_registry(
    connection: Any,
    database: str,
    base: str,
    manifest: MaterializationManifest,
    *,
    serving_variant_id: str | None = None,
    serving_variant_configuration_sha256: str | None = None,
) -> DorisRegistrySnapshot:
    """Require a complete, source-matching and count-matching publication."""
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    row = _fetch_registry_row(connection, table, manifest.source_identity.sha256)
    expected = _decode_counts(row.get("expected_counts_json"))
    observed = _decode_counts(row.get("observed_counts_json"))
    _validate_registry_identity(row, expected, observed, manifest)
    _validate_registry_variant(
        row,
        serving_variant_id,
        serving_variant_configuration_sha256,
    )
    actual_variant = row.get("serving_variant_id")
    actual_configuration = row.get("serving_variant_configuration_sha256")
    return DorisRegistrySnapshot(
        str(row["source_id"]),
        str(row["schema_version"]),
        str(row["status"]),
        expected,
        observed,
        None if actual_variant is None else str(actual_variant),
        None if actual_configuration is None else str(actual_configuration),
    )


def _fetch_registry_row(connection: Any, table: str, source_id: str) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT source_id, schema_version, expected_counts_json, observed_counts_json, "
            f"status, serving_variant_id, serving_variant_configuration_sha256, "
            f"registry_schema_version FROM {table} "
            "WHERE source_id = %s ORDER BY published_at DESC, manifest_path DESC LIMIT 1",
            (source_id,),
        )
        rows = cursor.fetchall()
        columns = tuple(str(column[0]) for column in cursor.description)
    if not rows:
        raise RuntimeError(
            "Doris serving projection is unavailable: no complete registry row for source "
            f"{source_id}"
        )
    return dict(zip(columns, rows[0], strict=True))


def _validate_registry_identity(
    row: dict[str, object],
    expected: dict[str, int],
    observed: dict[str, int],
    manifest: MaterializationManifest,
) -> None:
    if (
        row.get("status") != "complete"
        or row.get("schema_version") != manifest.schema_version
        or row.get("registry_schema_version") != REGISTRY_SCHEMA_VERSION
    ):
        raise RuntimeError("Doris serving projection is stale or incomplete")
    if expected != _expected_counts(manifest) or observed != expected:
        raise RuntimeError(
            "Doris serving projection is stale: registry counts do not match the manifest"
        )


def _validate_registry_variant(
    row: dict[str, object],
    serving_variant_id: str | None,
    serving_variant_configuration_sha256: str | None,
) -> None:
    actual_variant = row.get("serving_variant_id")
    if serving_variant_id is not None and actual_variant != serving_variant_id:
        raise RuntimeError("Doris serving projection variant does not match the requested variant")
    actual_configuration = row.get("serving_variant_configuration_sha256")
    if (
        serving_variant_configuration_sha256 is not None
        and actual_configuration != serving_variant_configuration_sha256
    ):
        raise RuntimeError(
            "Doris serving projection configuration does not match the requested variant"
        )


def _expected_counts(manifest: MaterializationManifest) -> dict[str, int]:
    return {family: manifest.counts.get(family, 0) for family in _FAMILIES}


def _observed_counts(connection: Any, database: str, base: str, source_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        for family in _FAMILIES:
            table = f"{_identifier(database)}.{_identifier(_family_table(base, family))}"
            cursor.execute(
                f"SELECT COUNT(*) AS row_count FROM {table} WHERE source_id = %s", (source_id,)
            )
            row = cursor.fetchall()[0]
            counts[family] = int(row[0])
    return counts


def _decode_counts(value: object) -> dict[str, int]:
    if not isinstance(value, str):
        raise RuntimeError("Doris registry count payload is malformed")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeError("Doris registry count payload is not valid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Doris registry count payload must be an object")
    return {str(key): int(item) for key, item in payload.items()}

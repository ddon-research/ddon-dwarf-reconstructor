"""Publication registry for complete source-bound Doris projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import MaterializationManifest
from .doris_layout import _FAMILIES, _family_table, _identifier


@dataclass(frozen=True, slots=True)
class DorisRegistrySnapshot:
    """Validated serving-projection publication metadata."""

    source_id: str
    schema_version: str
    status: str
    expected_counts: dict[str, int]
    observed_counts: dict[str, int]


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
    published_at DATETIME
) ENGINE=OLAP
DUPLICATE KEY(source_id)
DISTRIBUTED BY HASH(source_id) BUCKETS 3
PROPERTIES ("replication_num" = "1", "compression" = "zstd")"""


def publish_registry(
    connection: Any,
    database: str,
    base: str,
    manifest_path: Path,
    manifest: MaterializationManifest,
) -> DorisRegistrySnapshot:
    """Count every source family and publish only a complete reconciliation."""
    expected = _expected_counts(manifest)
    observed = _observed_counts(connection, database, base, manifest.source_identity.sha256)
    if observed != expected:
        _delete_registry_row(connection, database, base, manifest.source_identity.sha256)
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
    )
    _delete_registry_row(connection, database, base, source_id)
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} (source_id, schema_version, source_path, manifest_path, "
            "expected_counts_json, observed_counts_json, status, published_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
            payload,
        )
    return DorisRegistrySnapshot(source_id, manifest.schema_version, "complete", expected, observed)


def validate_registry(
    connection: Any,
    database: str,
    base: str,
    manifest: MaterializationManifest,
) -> DorisRegistrySnapshot:
    """Require a complete, source-matching and count-matching publication."""
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT source_id, schema_version, expected_counts_json, observed_counts_json, status "
            f"FROM {table} WHERE source_id = %s LIMIT 1",
            (manifest.source_identity.sha256,),
        )
        rows = cursor.fetchall()
        columns = tuple(str(column[0]) for column in cursor.description)
    if not rows:
        raise RuntimeError(
            "Doris serving projection is unavailable: no complete registry row for source "
            f"{manifest.source_identity.sha256}"
        )
    row = dict(zip(columns, rows[0], strict=True))
    expected = _decode_counts(row.get("expected_counts_json"))
    observed = _decode_counts(row.get("observed_counts_json"))
    manifest_counts = _expected_counts(manifest)
    if row.get("status") != "complete" or row.get("schema_version") != manifest.schema_version:
        raise RuntimeError("Doris serving projection is stale or incomplete")
    if expected != manifest_counts or observed != expected:
        raise RuntimeError(
            "Doris serving projection is stale: registry counts do not match the manifest"
        )
    return DorisRegistrySnapshot(
        str(row["source_id"]),
        str(row["schema_version"]),
        str(row["status"]),
        expected,
        observed,
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


def _delete_registry_row(connection: Any, database: str, base: str, source_id: str) -> None:
    table = f"{_identifier(database)}.{_identifier(registry_table(base))}"
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE source_id = %s", (source_id,))


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

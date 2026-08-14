"""Explicit Doris registry migration and publication ordering tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris_layout import _FAMILIES
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_registry import (
    REGISTRY_SCHEMA_VERSION,
    migrate_registry_schema,
    publish_registry,
    registry_migration_sql,
    validate_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]

SOURCE_ID = "a" * 64


def test_registry_migration_is_explicit_and_idempotent() -> None:
    statements = registry_migration_sql(
        "analytical",
        "dwarf",
        existing_columns={
            "source_id",
            "schema_version",
            "serving_variant_id",
        },
    )

    assert len(statements) == 2
    assert all("IF NOT EXISTS" not in statement for statement in statements)
    assert (
        registry_migration_sql(
            "analytical",
            "dwarf",
            existing_columns={
                "serving_variant_id",
                "serving_variant_configuration_sha256",
                "registry_schema_version",
            },
        )
        == ()
    )


def test_registry_migration_inspects_columns_before_altering() -> None:
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("source_id",),
        ("schema_version",),
        ("serving_variant_id",),
    ]
    cursor.__enter__.return_value = cursor
    connection = MagicMock()
    connection.cursor.return_value = cursor

    migrate_registry_schema(connection, "analytical", "dwarf")

    calls = [call.args[0] for call in cursor.execute.call_args_list]
    assert calls[0] == "SHOW COLUMNS FROM `analytical`.`dwarf_registry`"
    assert calls[1:] == [
        "ALTER TABLE `analytical`.`dwarf_registry` ADD COLUMN serving_variant_configuration_sha256 CHAR(64)",
        "ALTER TABLE `analytical`.`dwarf_registry` ADD COLUMN registry_schema_version VARCHAR(16) DEFAULT 'legacy'",
    ]


def test_registry_replacement_is_insert_before_legacy_cleanup(tmp_path: Path) -> None:
    counts = {family: 0 for family in _FAMILIES}
    count_cursor = MagicMock()
    count_cursor.__enter__.return_value = count_cursor
    count_cursor.fetchall.side_effect = [[(0,)] for _ in _FAMILIES]
    publish_cursor = MagicMock()
    publish_cursor.__enter__.return_value = publish_cursor
    connection = MagicMock()
    connection.cursor.side_effect = [count_cursor, publish_cursor]
    manifest = SimpleNamespace(
        source_identity=SimpleNamespace(sha256=SOURCE_ID),
        schema_version="1.1",
        source_path="source.elf",
        counts=counts,
    )

    result = publish_registry(
        connection,
        "analytical",
        "dwarf",
        tmp_path / "manifest.json",
        manifest,
        serving_variant_id="canonical",
        serving_variant_configuration_sha256="b" * 64,
    )

    assert result.status == "complete"
    insert, cleanup_legacy, cleanup_null, cleanup_current = publish_cursor.execute.call_args_list
    assert insert.args[0].startswith("INSERT INTO")
    assert cleanup_legacy.args[0].startswith("DELETE FROM")
    assert cleanup_null.args[0].startswith("DELETE FROM")
    assert "manifest_path <>" in cleanup_current.args[0]
    assert json.loads(insert.args[1][4]) == counts
    assert insert.args[1][9] == REGISTRY_SCHEMA_VERSION


def test_registry_validation_rejects_missing_publication() -> None:
    manifest = SimpleNamespace(
        source_identity=SimpleNamespace(sha256=SOURCE_ID),
        schema_version="1.1",
        counts={"unit": 1},
    )
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = ()
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with pytest.raises(RuntimeError, match="unavailable"):
        validate_registry(connection, "analytical", "dwarf", manifest)


def test_registry_validation_rejects_legacy_schema_rows() -> None:
    manifest = SimpleNamespace(
        source_identity=SimpleNamespace(sha256=SOURCE_ID),
        schema_version="1.1",
        counts={family: 0 for family in _FAMILIES},
    )
    counts = json.dumps(manifest.counts, sort_keys=True, separators=(",", ":"))
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = (
        (SOURCE_ID, "1.1", counts, counts, "complete", "canonical", "b" * 64, "legacy"),
    )
    cursor.description = (
        ("source_id",),
        ("schema_version",),
        ("expected_counts_json",),
        ("observed_counts_json",),
        ("status",),
        ("serving_variant_id",),
        ("serving_variant_configuration_sha256",),
        ("registry_schema_version",),
    )
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with pytest.raises(RuntimeError, match="stale or incomplete"):
        validate_registry(connection, "analytical", "dwarf", manifest)

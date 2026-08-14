"""Native Doris DDL and canonical family layout definitions."""

from __future__ import annotations

from typing import Any

from .doris_layout import _FAMILIES, _family_table, _identifier
from .doris_registry import registry_sql
from .doris_schema import _FAMILY_COLUMNS


def _native_sql(config: Any) -> list[str]:
    """Build the idempotent native family and serving-table DDL."""
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
    if config.uses_promoted_name_lookup:
        statements.append(_promoted_name_lookup_sql(config))
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


def _promoted_name_lookup_sql(config: Any) -> str:
    """Build the canonical source/name lookup table DDL."""
    database = _identifier(config.database)
    table = _identifier(config.effective_name_lookup_table)
    return f"""CREATE TABLE IF NOT EXISTS {database}.{table} (
    source_id CHAR(64) NOT NULL,
    name VARCHAR(1024),
    unit_offset BIGINT NOT NULL,
    die_offset BIGINT NOT NULL,
    index_type VARCHAR(64) NOT NULL,
    tag VARCHAR(128),
    target_offset BIGINT,
    resolution_status VARCHAR(32)
) ENGINE=OLAP
DUPLICATE KEY(source_id, name, unit_offset, die_offset)
DISTRIBUTED BY HASH(source_id, name) BUCKETS 8
PROPERTIES ("replication_num" = "1", "compression" = "zstd")"""


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


__all__ = [
    "_FAMILY_BLOOM_COLUMNS",
    "_FAMILY_DISTRIBUTION",
    "_FAMILY_KEYS",
    "_native_columns",
    "_native_sql",
]

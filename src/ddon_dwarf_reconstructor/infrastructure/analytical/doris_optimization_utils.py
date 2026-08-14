"""Small serialization, hashing, and profile helpers for Doris evidence."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .doris import DorisConfig


def last_query_id(connection: Any) -> tuple[str | None, str | None]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT last_query_id()")
            rows = cursor.fetchall()
        if not rows or not rows[0] or rows[0][0] in (None, ""):
            return None, None
        return str(rows[0][0]), None
    except Exception as error:  # tracing must never alter the measured query result
        return None, str(error)


def configured_ddl_sha256(config: DorisConfig) -> str:
    """Hash the exact canonical native DDL from the typed Doris configuration."""
    return config.ddl_sha256()


def mapping(value: object) -> dict[str, object]:
    return {str(key): item for key, item in value.items()} if isinstance(value, Mapping) else {}


def json_default(value: object) -> str:
    """Serialize typed Doris evidence values deterministically."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def int_mapping(value: object) -> dict[str, int]:
    return {
        key: int(item)
        for key, item in mapping(value).items()
        if isinstance(item, (int, float, str)) and str(item).lstrip("-").isdigit()
    }


def query_shape(sql: str) -> str:
    compact = re.sub(r"\s+", " ", sql.strip())
    return re.sub(r"\b\d+\b", "?", compact)


def profile_metrics(summary: Mapping[str, object]) -> dict[str, object]:
    aliases = {
        "scan_bytes": ("scan_bytes", "bytes_read", "bytes_scanned"),
        "scan_rows": ("scan_rows", "rows_scanned"),
        "tablet_count": ("tablet_count", "tablets"),
        "schedule_seconds": ("schedule_seconds", "schedule_time"),
        "operator_seconds": ("operator_seconds", "operator_time", "elapsed_seconds"),
        "peak_memory_bytes": ("peak_memory_bytes", "peak_memory", "memory"),
        "spill_bytes": ("spill_bytes", "spilled", "spill"),
    }
    flattened = {key.lower(): value for key, value in flatten_mapping(summary)}
    return {
        name: next((flattened[key] for key in keys if key in flattened), None)
        for name, keys in aliases.items()
    }


def flatten_mapping(value: object, prefix: str = "") -> list[tuple[str, object]]:
    if not isinstance(value, Mapping):
        return []
    result: list[tuple[str, object]] = []
    for key, item in value.items():
        name = str(key)
        result.append((name, item))
        result.extend(flatten_mapping(item, f"{prefix}{name}."))
    return result


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2, default=json_default)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)

"""Restore logical analytical rows returned by the Doris serving tables."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

_VALUE_SUFFIXES = (
    "kind",
    "bool",
    "int",
    "uint",
    "float",
    "text",
    "binary",
    "json",
    "path",
    "sha256",
    "size",
)
_SEMANTIC_KINDS = frozenset({"range", "location", "line", "macro", "frame", "abbreviation", "name"})
_UNSIGNED_FIELDS = frozenset(
    {"start_address", "end_address", "base_address", "address", "initial_address", "address_range"}
)


def restore_row(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the logical row shape consumed by the Doris adapter."""
    kind = str(row.get("record_type", ""))
    result = dict(row)
    result.pop("unit_bucket", None)
    if kind == "unit":
        result["header"] = _json_load(row.get("header_json"), {})
        result["details"] = _json_load(row.get("details_json"), None)
        result.pop("header_json", None)
        result.pop("details_json", None)
    elif kind == "attribute":
        result["raw_value"] = restore_value(row, "raw_value")
        result["decoded_value"] = restore_value(row, "decoded_value")
        _drop_value_columns(result, "raw_value")
        _drop_value_columns(result, "decoded_value")
    elif kind in {"reference", "index"}:
        result["raw_target"] = restore_value(row, "raw_target")
        _drop_value_columns(result, "raw_target")
    elif kind in _SEMANTIC_KINDS:
        result["details"] = _json_load(row.get("details_json"), None)
        result.pop("details_json", None)
        for field in _UNSIGNED_FIELDS:
            if isinstance(result.get(field), Decimal):
                result[field] = int(result[field])
    return result


def restore_value(row: dict[str, Any], prefix: str) -> Any:
    """Restore one typed scalar or its lossless JSON fallback."""
    kind = row.get(f"{prefix}_kind")
    if kind in {None, "null"}:
        return None
    if kind == "bool":
        return row.get(f"{prefix}_bool")
    if kind == "int":
        return row.get(f"{prefix}_int")
    if kind == "uint":
        return _integer_value(row.get(f"{prefix}_uint"))
    if kind == "float":
        return row.get(f"{prefix}_float")
    if kind == "text":
        return row.get(f"{prefix}_text")
    if kind == "bytes":
        return row.get(f"{prefix}_binary")
    return _json_load(row.get(f"{prefix}_json"), None)


def _drop_value_columns(row: dict[str, Any], prefix: str) -> None:
    for suffix in _VALUE_SUFFIXES:
        row.pop(f"{prefix}_{suffix}", None)


def _json_load(value: Any, default: Any) -> Any:
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _integer_value(value: Any) -> int | None:
    if isinstance(value, Decimal):
        return int(value)
    return value if isinstance(value, int) and not isinstance(value, bool) else None

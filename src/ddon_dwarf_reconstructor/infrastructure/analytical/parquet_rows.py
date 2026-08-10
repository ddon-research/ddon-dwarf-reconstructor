"""Family-specific Arrow rows for the analytical DWARF store."""

from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

from .semantic_rows import normalize_record as normalize_semantic_record
from .semantic_rows import schema_fields as semantic_schema_fields

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
_UNSIGNED_SEMANTIC_FIELDS = frozenset(
    {
        "start_address",
        "end_address",
        "base_address",
        "address",
        "initial_address",
        "address_range",
    }
)


def schema_for(pyarrow: Any, kind: str) -> Any:
    """Return the stable nullable schema for one normalized record family."""
    factories = {
        "section": _section_fields,
        "raw_chunk": _raw_chunk_fields,
        "unit": _unit_fields,
        "die": _die_fields,
        "attribute": _attribute_fields,
        "reference": _reference_fields,
        "index": _index_fields,
    }
    try:
        fields = (
            semantic_schema_fields(pyarrow, kind)
            if kind in _SEMANTIC_KINDS
            else factories[kind](pyarrow)
        )
    except KeyError as error:
        raise ValueError(f"Unsupported analytical record family: {kind}") from error
    return pyarrow.schema(
        [
            pyarrow.field(name, arrow_type, nullable=nullable)
            for name, arrow_type, nullable in fields
        ]
    )


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Project a logical row into a family-specific, columnar representation."""
    kind = str(record.get("record_type", ""))
    try:
        return (
            normalize_semantic_record(record)
            if kind in _SEMANTIC_KINDS
            else _ROW_BUILDERS[kind](record)
        )
    except KeyError as error:
        raise ValueError(f"Unsupported analytical record family: {kind}") from error


def _field(pyarrow: Any, name: str, arrow_type: Any) -> tuple[str, Any, bool]:
    return name, arrow_type, True


def _required_field(pyarrow: Any, name: str, arrow_type: Any) -> tuple[str, Any, bool]:
    del pyarrow
    return name, arrow_type, False


def _common_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return [
        _required_field(pyarrow, "record_type", pyarrow.string()),
        _field(pyarrow, "source_id", pyarrow.string()),
    ]


def _section_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field(pyarrow, "section_index", pyarrow.int64()),
        _field(pyarrow, "section_name", pyarrow.string()),
        _field(pyarrow, "file_offset", pyarrow.int64()),
        _field(pyarrow, "file_size", pyarrow.int64()),
        _field(pyarrow, "raw_path", pyarrow.string()),
        _field(pyarrow, "raw_sha256", pyarrow.string()),
        _field(pyarrow, "chunk_size", pyarrow.int64()),
        _field(pyarrow, "chunk_count", pyarrow.int64()),
    ]


def _raw_chunk_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field(pyarrow, "section_index", pyarrow.int64()),
        _field(pyarrow, "section_name", pyarrow.string()),
        _field(pyarrow, "raw_path", pyarrow.string()),
        _field(pyarrow, "chunk_index", pyarrow.int64()),
        _field(pyarrow, "byte_offset", pyarrow.int64()),
        _field(pyarrow, "byte_size", pyarrow.int64()),
        _field(pyarrow, "file_offset", pyarrow.int64()),
        _field(pyarrow, "raw_sha256", pyarrow.string()),
    ]


def _unit_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field(pyarrow, "unit_offset", pyarrow.int64()),
        _field(pyarrow, "unit_bucket", pyarrow.int64()),
        _field(pyarrow, "unit_length", pyarrow.int64()),
        _field(pyarrow, "unit_type", pyarrow.string()),
        _field(pyarrow, "header_json", pyarrow.string()),
        _field(pyarrow, "parser_status", pyarrow.string()),
        _field(pyarrow, "details_json", pyarrow.string()),
    ]


def _die_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field(pyarrow, "unit_offset", pyarrow.int64()),
        _field(pyarrow, "unit_bucket", pyarrow.int64()),
        _field(pyarrow, "die_offset", pyarrow.int64()),
        _field(pyarrow, "ordinal", pyarrow.int64()),
        _field(pyarrow, "tag", pyarrow.string()),
        _field(pyarrow, "abbrev_code", pyarrow.int64()),
        _field(pyarrow, "has_children", pyarrow.bool_()),
        _field(pyarrow, "depth", pyarrow.int64()),
        _field(pyarrow, "parent_offset", pyarrow.int64()),
        _field(pyarrow, "is_null", pyarrow.bool_()),
    ]


def _attribute_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return (
        _common_fields(pyarrow)
        + _attribute_key_fields(pyarrow)
        + [
            *_value_fields(pyarrow, "raw_value"),
            *_value_fields(pyarrow, "decoded_value"),
        ]
    )


def _attribute_key_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return [
        _field(pyarrow, "unit_offset", pyarrow.int64()),
        _field(pyarrow, "unit_bucket", pyarrow.int64()),
        _field(pyarrow, "die_offset", pyarrow.int64()),
        _field(pyarrow, "ordinal", pyarrow.int64()),
        _field(pyarrow, "name", pyarrow.string()),
        _field(pyarrow, "form", pyarrow.string()),
        _field(pyarrow, "value_offset", pyarrow.int64()),
        _field(pyarrow, "indirection_length", pyarrow.int64()),
    ]


def _reference_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return (
        _common_fields(pyarrow)
        + _reference_key_fields(pyarrow)
        + [
            *_value_fields(pyarrow, "raw_target"),
            _field(pyarrow, "target_offset", pyarrow.int64()),
            _field(pyarrow, "resolution_status", pyarrow.string()),
        ]
    )


def _reference_key_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return [
        _field(pyarrow, "unit_offset", pyarrow.int64()),
        _field(pyarrow, "unit_bucket", pyarrow.int64()),
        _field(pyarrow, "die_offset", pyarrow.int64()),
        _field(pyarrow, "attribute_name", pyarrow.string()),
        _field(pyarrow, "relation", pyarrow.string()),
    ]


def _index_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field(pyarrow, "unit_offset", pyarrow.int64()),
        _field(pyarrow, "unit_bucket", pyarrow.int64()),
        _field(pyarrow, "die_offset", pyarrow.int64()),
        _field(pyarrow, "index_type", pyarrow.string()),
        _field(pyarrow, "name", pyarrow.string()),
        _field(pyarrow, "tag", pyarrow.string()),
        *_value_fields(pyarrow, "raw_target"),
        _field(pyarrow, "target_offset", pyarrow.int64()),
        _field(pyarrow, "resolution_status", pyarrow.string()),
    ]


def _base_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": str(record.get("record_type", "")),
        "source_id": _string(record.get("source_id")),
    }


def _section_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "section_index": _int(record.get("section_index")),
        "section_name": _string(record.get("section_name")),
        "file_offset": _uint(record.get("file_offset")),
        "file_size": _uint(record.get("file_size")),
        "raw_path": _string(record.get("raw_path")),
        "raw_sha256": _string(record.get("raw_sha256")),
        "chunk_size": _uint(record.get("chunk_size")),
        "chunk_count": _uint(record.get("chunk_count")),
    }


def _raw_chunk_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "section_index": _int(record.get("section_index")),
        "section_name": _string(record.get("section_name")),
        "raw_path": _string(record.get("raw_path")),
        "chunk_index": _int(record.get("chunk_index")),
        "byte_offset": _uint(record.get("byte_offset")),
        "byte_size": _uint(record.get("byte_size")),
        "file_offset": _uint(record.get("file_offset")),
        "raw_sha256": _string(record.get("raw_sha256")),
    }


def _unit_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "unit_length": _uint(record.get("unit_length")),
        "unit_type": _string(record.get("unit_type")),
        "header_json": _json_text(record.get("header")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _die_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "ordinal": _int(record.get("ordinal")),
        "tag": _string(record.get("tag")),
        "abbrev_code": _int(record.get("abbrev_code")),
        "has_children": _bool(record.get("has_children")),
        "depth": _int(record.get("depth")),
        "parent_offset": _uint(record.get("parent_offset")),
        "is_null": _bool(record.get("is_null")),
    }


def _attribute_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "ordinal": _int(record.get("ordinal")),
        "name": _string(record.get("name")),
        "form": _string(record.get("form")),
        "value_offset": _uint(record.get("value_offset")),
        "indirection_length": _uint(record.get("indirection_length")),
        **_value_columns("raw_value", record.get("raw_value")),
        **_value_columns("decoded_value", record.get("decoded_value")),
    }


def _reference_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "attribute_name": _string(record.get("attribute_name")),
        "relation": _string(record.get("relation")),
        **_value_columns("raw_target", record.get("raw_target")),
        "target_offset": _uint(record.get("target_offset")),
        "resolution_status": _string(record.get("resolution_status")),
    }


def _index_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "index_type": _string(record.get("index_type")),
        "name": _string(record.get("name")),
        "tag": _string(record.get("tag")),
        **_value_columns("raw_target", record.get("raw_target")),
        "target_offset": _uint(record.get("target_offset")),
        "resolution_status": _string(record.get("resolution_status")),
    }


def restore_record(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the logical row shape consumed by the query adapters."""
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
    elif kind in {"range", "location", "line", "macro", "frame", "abbreviation", "name"}:
        result["details"] = _json_load(row.get("details_json"), None)
        result.pop("details_json", None)
        for field in _UNSIGNED_SEMANTIC_FIELDS:
            if isinstance(result.get(field), Decimal):
                result[field] = int(result[field])
    return result


def restore_value(row: dict[str, Any], prefix: str) -> Any:
    """Restore a typed scalar or the exact tagged fallback value."""
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


def _value_fields(pyarrow: Any, prefix: str) -> list[tuple[str, Any, bool]]:
    types = {
        "kind": pyarrow.string(),
        "bool": pyarrow.bool_(),
        "int": pyarrow.int64(),
        "uint": pyarrow.decimal128(20, 0),
        "float": pyarrow.float64(),
        "text": pyarrow.string(),
        "binary": pyarrow.binary(),
        "json": pyarrow.string(),
        "path": pyarrow.string(),
        "sha256": pyarrow.string(),
        "size": pyarrow.decimal128(20, 0),
    }
    return [(f"{prefix}_{suffix}", types[suffix], True) for suffix in _VALUE_SUFFIXES]


def _value_columns(prefix: str, value: Any) -> dict[str, Any]:
    columns: dict[str, Any] = {f"{prefix}_{suffix}": None for suffix in _VALUE_SUFFIXES}
    if value is None:
        columns[f"{prefix}_kind"] = "null"
    else:
        scalar = _scalar_value_columns(prefix, value)
        if scalar is not None:
            columns.update(scalar)
        elif isinstance(value, dict):
            columns.update(_mapping_value_columns(prefix, value))
        else:
            columns[f"{prefix}_kind"] = "json"
            columns[f"{prefix}_json"] = _json_text(value)
    return columns


def _scalar_value_columns(prefix: str, value: Any) -> dict[str, Any] | None:
    if isinstance(value, bool):
        return {f"{prefix}_kind": "bool", f"{prefix}_bool": value}
    if isinstance(value, int):
        if value < -(2**63) or value > 2**64 - 1:
            return {
                f"{prefix}_kind": "bigint",
                f"{prefix}_json": _json_text(value),
            }
        suffix = "int" if value < 0 else "uint"
        stored = value if suffix == "int" else Decimal(value)
        return {f"{prefix}_kind": suffix, f"{prefix}_{suffix}": stored}
    if isinstance(value, float):
        return {f"{prefix}_kind": "float", f"{prefix}_float": value}
    if isinstance(value, str):
        return {f"{prefix}_kind": "text", f"{prefix}_text": value}
    return None


def _mapping_value_columns(prefix: str, value: dict[str, Any]) -> dict[str, Any]:
    if value.get("type") == "external_bytes":
        return {
            f"{prefix}_kind": "external_bytes",
            f"{prefix}_path": _string(value.get("path")),
            f"{prefix}_sha256": _string(value.get("sha256")),
            f"{prefix}_size": _decimal(value.get("size")),
            f"{prefix}_json": _json_text(value),
        }
    if value.get("kind") == "bytes":
        return _bytes_value_columns(prefix, value)
    return {
        f"{prefix}_kind": str(value.get("kind", "json")),
        f"{prefix}_json": _json_text(value),
    }


def _bytes_value_columns(prefix: str, value: dict[str, Any]) -> dict[str, Any]:
    encoded = value.get("value")
    binary = (
        base64.b64decode(encoded.encode("ascii"), validate=True)
        if isinstance(encoded, str)
        else None
    )
    return {
        f"{prefix}_kind": "bytes",
        f"{prefix}_binary": binary,
        f"{prefix}_json": _bytes_json_text(encoded, value),
    }


def _drop_value_columns(row: dict[str, Any], prefix: str) -> None:
    for suffix in _VALUE_SUFFIXES:
        row.pop(f"{prefix}_{suffix}", None)


def _json_text(value: Any) -> str | None:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if value is not None
        else None
    )


def _bytes_json_text(encoded: Any, value: dict[str, Any]) -> str:
    """Serialize the common tagged-byte shape without re-encoding its payload.

    ``tag_value`` already produced a base64 ASCII payload.  Keeping the
    canonical sorted-key spelling avoids a Python JSON encoder call for every
    byte-valued DWARF attribute while preserving the lossless JSON contract.
    Malformed external rows still use the general serializer.
    """
    if isinstance(encoded, str):
        return f'{{"encoding":"base64","kind":"bytes","value":"{encoded}"}}'
    serialized = _json_text(value)
    return serialized if serialized is not None else "{}"


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


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _uint(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _decimal(value: Any) -> Decimal | None:
    integer = _uint(value)
    return Decimal(integer) if integer is not None else None


def _unit_bucket(value: Any) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value // 0x1000000


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


_ROW_BUILDERS = {
    "section": _section_row,
    "raw_chunk": _raw_chunk_row,
    "unit": _unit_row,
    "die": _die_row,
    "attribute": _attribute_row,
    "reference": _reference_row,
    "index": _index_row,
}

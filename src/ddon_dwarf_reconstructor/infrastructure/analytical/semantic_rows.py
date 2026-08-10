"""Arrow schemas for range, location, line, macro, frame, and name records."""

from __future__ import annotations

import json
from typing import Any


def schema_fields(pyarrow: Any, kind: str) -> list[tuple[str, Any, bool]]:
    try:
        return _SCHEMA_FACTORIES[kind](pyarrow)
    except KeyError as error:
        raise ValueError(f"Unsupported semantic record family: {kind}") from error


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    kind = str(record.get("record_type", ""))
    try:
        return _ROW_BUILDERS[kind](record)
    except KeyError as error:
        raise ValueError(f"Unsupported semantic record family: {kind}") from error


def _field(name: str, arrow_type: Any) -> tuple[str, Any, bool]:
    return name, arrow_type, True


def _common_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return [
        ("record_type", pyarrow.string(), False),
        _field("source_id", pyarrow.string()),
    ]


def _semantic_identity_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return [
        _field("unit_offset", pyarrow.int64()),
        _field("unit_bucket", pyarrow.int64()),
        _field("die_offset", pyarrow.int64()),
        _field("ordinal", pyarrow.int64()),
        _field("attribute_name", pyarrow.string()),
        _field("record_offset", pyarrow.int64()),
        _field("record_length", pyarrow.int64()),
        _field("entry_kind", pyarrow.string()),
        _field("parser_status", pyarrow.string()),
        _field("details_json", pyarrow.string()),
    ]


def _range_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return (
        _common_fields(pyarrow)
        + _semantic_identity_fields(pyarrow)
        + [
            _field("start_address", pyarrow.decimal128(20, 0)),
            _field("end_address", pyarrow.decimal128(20, 0)),
            _field("base_address", pyarrow.decimal128(20, 0)),
            _field("is_absolute", pyarrow.bool_()),
        ]
    )


def _location_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return (
        _common_fields(pyarrow)
        + _semantic_identity_fields(pyarrow)
        + [
            _field("start_address", pyarrow.decimal128(20, 0)),
            _field("end_address", pyarrow.decimal128(20, 0)),
            _field("is_absolute", pyarrow.bool_()),
            _field("expression_json", pyarrow.string()),
        ]
    )


def _line_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field("unit_offset", pyarrow.int64()),
        _field("unit_bucket", pyarrow.int64()),
        _field("ordinal", pyarrow.int64()),
        _field("entry_kind", pyarrow.string()),
        _field("program_offset", pyarrow.int64()),
        _field("record_offset", pyarrow.int64()),
        _field("command", pyarrow.int64()),
        _field("address", pyarrow.decimal128(20, 0)),
        _field("file_index", pyarrow.int64()),
        _field("directory_index", pyarrow.int64()),
        _field("source_file", pyarrow.string()),
        _field("directory", pyarrow.string()),
        _field("line", pyarrow.int64()),
        _field("column", pyarrow.int64()),
        _field("op_index", pyarrow.int64()),
        _field("is_stmt", pyarrow.bool_()),
        _field("basic_block", pyarrow.bool_()),
        _field("end_sequence", pyarrow.bool_()),
        _field("prologue_end", pyarrow.bool_()),
        _field("epilogue_begin", pyarrow.bool_()),
        _field("isa", pyarrow.int64()),
        _field("discriminator", pyarrow.int64()),
        _field("details_json", pyarrow.string()),
    ]


def _macro_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field("section_name", pyarrow.string()),
        _field("record_offset", pyarrow.int64()),
        _field("record_length", pyarrow.int64()),
        _field("macro_kind", pyarrow.string()),
        _field("raw_path", pyarrow.string()),
        _field("raw_sha256", pyarrow.string()),
        _field("parser_status", pyarrow.string()),
        _field("details_json", pyarrow.string()),
    ]


def _frame_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field("section_name", pyarrow.string()),
        _field("record_offset", pyarrow.int64()),
        _field("record_length", pyarrow.int64()),
        _field("frame_kind", pyarrow.string()),
        _field("initial_address", pyarrow.decimal128(20, 0)),
        _field("address_range", pyarrow.decimal128(20, 0)),
        _field("parser_status", pyarrow.string()),
        _field("details_json", pyarrow.string()),
    ]


def _abbreviation_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field("unit_offset", pyarrow.int64()),
        _field("unit_bucket", pyarrow.int64()),
        _field("record_offset", pyarrow.int64()),
        _field("abbrev_code", pyarrow.int64()),
        _field("tag", pyarrow.string()),
        _field("has_children", pyarrow.bool_()),
        _field("parser_status", pyarrow.string()),
        _field("details_json", pyarrow.string()),
    ]


def _name_fields(pyarrow: Any) -> list[tuple[str, Any, bool]]:
    return _common_fields(pyarrow) + [
        _field("unit_offset", pyarrow.int64()),
        _field("unit_bucket", pyarrow.int64()),
        _field("die_offset", pyarrow.int64()),
        _field("ordinal", pyarrow.int64()),
        _field("name", pyarrow.string()),
        _field("name_kind", pyarrow.string()),
        _field("attribute_name", pyarrow.string()),
        _field("parser_status", pyarrow.string()),
        _field("details_json", pyarrow.string()),
    ]


def _base_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": str(record.get("record_type", "")),
        "source_id": _string(record.get("source_id")),
    }


def _semantic_identity_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "ordinal": _int(record.get("ordinal")),
        "attribute_name": _string(record.get("attribute_name")),
        "record_offset": _uint(record.get("record_offset")),
        "record_length": _uint(record.get("record_length")),
        "entry_kind": _string(record.get("entry_kind")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _range_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        **_semantic_identity_row(record),
        "start_address": _uint(record.get("start_address")),
        "end_address": _uint(record.get("end_address")),
        "base_address": _uint(record.get("base_address")),
        "is_absolute": _bool(record.get("is_absolute")),
    }


def _location_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        **_semantic_identity_row(record),
        "start_address": _uint(record.get("start_address")),
        "end_address": _uint(record.get("end_address")),
        "is_absolute": _bool(record.get("is_absolute")),
        "expression_json": _json_text(record.get("expression")),
    }


def _line_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "ordinal": _int(record.get("ordinal")),
        "entry_kind": _string(record.get("entry_kind")),
        "program_offset": _uint(record.get("program_offset")),
        "record_offset": _uint(record.get("record_offset")),
        "command": _int(record.get("command")),
        "address": _uint(record.get("address")),
        "file_index": _int(record.get("file_index")),
        "directory_index": _int(record.get("directory_index")),
        "source_file": _string(record.get("source_file")),
        "directory": _string(record.get("directory")),
        "line": _int(record.get("line")),
        "column": _int(record.get("column")),
        "op_index": _int(record.get("op_index")),
        "is_stmt": _bool(record.get("is_stmt")),
        "basic_block": _bool(record.get("basic_block")),
        "end_sequence": _bool(record.get("end_sequence")),
        "prologue_end": _bool(record.get("prologue_end")),
        "epilogue_begin": _bool(record.get("epilogue_begin")),
        "isa": _int(record.get("isa")),
        "discriminator": _int(record.get("discriminator")),
        "details_json": _json_text(record.get("details")),
    }


def _macro_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "section_name": _string(record.get("section_name")),
        "record_offset": _uint(record.get("record_offset")),
        "record_length": _uint(record.get("record_length")),
        "macro_kind": _string(record.get("macro_kind")),
        "raw_path": _string(record.get("raw_path")),
        "raw_sha256": _string(record.get("raw_sha256")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _frame_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "section_name": _string(record.get("section_name")),
        "record_offset": _uint(record.get("record_offset")),
        "record_length": _uint(record.get("record_length")),
        "frame_kind": _string(record.get("frame_kind")),
        "initial_address": _uint(record.get("initial_address")),
        "address_range": _uint(record.get("address_range")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _abbreviation_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "record_offset": _uint(record.get("record_offset")),
        "abbrev_code": _int(record.get("abbrev_code")),
        "tag": _string(record.get("tag")),
        "has_children": _bool(record.get("has_children")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _name_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **_base_row(record),
        "unit_offset": _uint(record.get("unit_offset")),
        "unit_bucket": _unit_bucket(record.get("unit_offset")),
        "die_offset": _uint(record.get("die_offset")),
        "ordinal": _int(record.get("ordinal")),
        "name": _string(record.get("name")),
        "name_kind": _string(record.get("name_kind")),
        "attribute_name": _string(record.get("attribute_name")),
        "parser_status": _string(record.get("parser_status")),
        "details_json": _json_text(record.get("details")),
    }


def _json_text(value: Any) -> str | None:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if value is not None
        else None
    )


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _uint(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _unit_bucket(value: Any) -> int | None:
    integer = _uint(value)
    return integer // 0x1000000 if integer is not None else None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


_SCHEMA_FACTORIES = {
    "range": _range_fields,
    "location": _location_fields,
    "line": _line_fields,
    "macro": _macro_fields,
    "frame": _frame_fields,
    "abbreviation": _abbreviation_fields,
    "name": _name_fields,
}
_ROW_BUILDERS = {
    "range": _range_row,
    "location": _location_row,
    "line": _line_row,
    "macro": _macro_row,
    "frame": _frame_row,
    "abbreviation": _abbreviation_row,
    "name": _name_row,
}

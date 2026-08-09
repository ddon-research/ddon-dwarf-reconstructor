"""Pure helpers for Doris diagnostic evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .doris_diagnostics_transport import DiagnosticTransportResult


def statement_identity(source_id: str, sql: str) -> str:
    """Return a stable source-bound identity for one exact SQL string."""
    return hashlib.sha256(f"{source_id}\0{sql}".encode()).hexdigest()


def normalize_plan_text(text: str) -> str:
    """Normalize whitespace while preserving plan token order."""
    return " ".join(text.split())


def ordered_result_sha256(rows: Sequence[object]) -> str:
    """Hash returned rows in order using typed JSON values."""
    encoded = json.dumps(
        [_safe_value(row) for row in rows], ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def typed_parameter_records(parameters: Sequence[object]) -> list[dict[str, object]]:
    """Retain parameter type and digest without publishing parameter values."""
    return [
        {"type": _type_name(value), "sha256": _canonical_hash(_safe_value(value))}
        for value in parameters
    ]


def render_sql_with_parameters(sql: str, parameters: Sequence[object]) -> str:
    """Render DB-API placeholders for EXPLAIN using typed, non-secret text."""
    rendered = sql
    for parameter in parameters:
        rendered = rendered.replace("%s", _sql_literal(parameter), 1)
    return rendered


def explain_summary(text: str) -> dict[str, object]:
    """Extract stable, bounded plan signals for schema comparisons."""
    lowered = text.lower()
    tables = sorted(set(re.findall(r"(?:table|olap scan|scan)[^\n]*?([`\w]+\.[`\w]+)", text, re.I)))
    predicates = [line.strip() for line in text.splitlines() if "predicate" in line.lower()]
    cardinality = [line.strip() for line in text.splitlines() if "cardinality" in line.lower()]
    tablets = [line.strip() for line in text.splitlines() if "tablet" in line.lower()]
    return {
        "table_names": tables,
        "predicate_lines": predicates[:50],
        "cardinality_lines": cardinality[:50],
        "tablet_lines": tablets[:50],
        "contains_join": " join " in f" {lowered} ",
    }


def profile_matches_query_id(payload: object | None, text: str, query_id: str) -> bool:
    """Reject a profile that cannot be associated with this execution."""
    if isinstance(payload, Mapping):
        values = [payload.get("query_id"), payload.get("queryId"), payload.get("Query ID")]
        if any(value is not None for value in values):
            return query_id in {str(value) for value in values if value is not None}
    return query_id in text


def _profile_status(raw: Mapping[str, object], full: Mapping[str, object]) -> str:
    statuses = {str(raw.get("status")), str(full.get("status"))}
    if statuses == {"observed"}:
        return "observed"
    if "blocked" in statuses:
        return "blocked"
    if statuses <= {"unavailable"}:
        return "unavailable"
    return "partial"


def _profile_summary(full: Mapping[str, object], raw: Mapping[str, object]) -> dict[str, object]:
    summary = full.get("summary") if isinstance(full.get("summary"), Mapping) else {}
    if summary:
        return _mapping_copy(summary)
    fallback = raw.get("summary") if isinstance(raw.get("summary"), Mapping) else {}
    return _mapping_copy(fallback)


def _profile_text_summary(text: str) -> dict[str, object]:
    patterns = {
        "query_id": r"(?im)^\s*query\s*id\s*[:=]\s*([^\s]+)",
        "elapsed_seconds": r"(?im)elapsed(?:\s*time)?\s*[:=]\s*([^\s]+)",
        "peak_memory": r"(?im)(?:peak\s+memory|memory)\s*[:=]\s*([^\s]+)",
        "rows": r"(?im)(?:rows|rows\s+returned)\s*[:=]\s*([^\s]+)",
        "scan_bytes": r"(?im)(?:scan\s+bytes|bytes\s+read)\s*[:=]\s*([^\s]+)",
        "spill": r"(?im)(?:spill|spilled)\s*[:=]\s*([^\s]+)",
    }
    return {
        name: match.group(1)
        for name, pattern in patterns.items()
        if (match := re.search(pattern, text))
    }


def _profile_payload_summary(payload: object | None, text: str) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        return _profile_text_summary(text)
    profile = payload.get("profile")
    if not isinstance(profile, Mapping):
        return _profile_text_summary(text)
    summary: dict[str, object] = {}
    for key in ("summary", "execution_summary", "changed_session_vars"):
        value = profile.get(key)
        if value is not None:
            summary[key] = _safe_value(value)
    operators = payload.get("operators")
    if isinstance(operators, Sequence) and not isinstance(operators, (str, bytes, bytearray)):
        summary["operator_count"] = len(operators)
    if "physical_plan" in payload:
        summary["physical_plan_present"] = bool(payload.get("physical_plan"))
    return summary or _profile_text_summary(text)


def _profile_json(result: DiagnosticTransportResult, text: str) -> object:
    if result.payload is not None:
        return result.payload
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_profile": text}


def _payload_text(payload: object | None, fallback: str) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        for key in ("profile", "raw_profile", "text", "data", "result"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        if "rows" in payload:
            return _rows_text(payload.get("rows", []))
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return _rows_text(payload)
    return fallback


def _rows_text(rows: object) -> str:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return str(rows) if rows else ""
    lines: list[str] = []
    for row in rows:
        if isinstance(row, Mapping):
            lines.append(" | ".join(str(value) for value in row.values()))
        elif isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
            lines.append(" | ".join(str(value) for value in row))
        else:
            lines.append(str(row))
    return "\n".join(lines)


def _diagnostic_failure_status(status: str) -> str:
    if status in {"blocked", "unavailable", "partial"}:
        return status
    return "partial"


def _attempts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _executions(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping_copy(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _aggregate_status(
    schema: Mapping[str, object],
    statements: Sequence[Mapping[str, object]],
    executions: Sequence[Mapping[str, object]],
    errors: Sequence[Mapping[str, object]],
) -> str:
    statuses = [str(schema.get("status", "not_observed"))]
    for statement in statements:
        statuses.extend(_explain_statuses(statement.get("explain", {})))
    statuses.extend(str(item.get("profile_status", "not_observed")) for item in executions)
    return _resolve_status(statuses, has_statements=bool(statements), has_errors=bool(errors))


def _explain_statuses(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return [
        str(item.get("status", "not_observed"))
        for item in value.values()
        if isinstance(item, Mapping)
    ]


def _resolve_status(statuses: list[str], *, has_statements: bool, has_errors: bool) -> str:
    if has_errors and "blocked" not in statuses:
        statuses.append("partial")
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses:
        return "partial"
    if "unavailable" in statuses:
        return "unavailable"
    if not has_statements:
        return "not_observed"
    return "observed"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        _safe_value(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_value(item) for item in value]
    return {"type": _type_name(value), "value": str(value)}


def _type_name(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "(" + ", ".join(_sql_literal(item) for item in value) + ")"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _identifier(value: str) -> str:
    if not value or not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{value}`"


__all__ = [
    "_aggregate_status",
    "_attempts",
    "_canonical_hash",
    "_diagnostic_failure_status",
    "_executions",
    "_identifier",
    "_payload_text",
    "_profile_json",
    "_profile_payload_summary",
    "_profile_status",
    "_profile_summary",
    "_profile_text_summary",
    "_rows_text",
    "_safe_value",
    "_sha256_text",
    "explain_summary",
    "normalize_plan_text",
    "ordered_result_sha256",
    "profile_matches_query_id",
    "render_sql_with_parameters",
    "statement_identity",
    "typed_parameter_records",
]

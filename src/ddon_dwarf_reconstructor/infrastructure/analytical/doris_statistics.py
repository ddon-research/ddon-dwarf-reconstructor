"""Doris statistics lifecycle and terminal-state evidence."""

from __future__ import annotations

from time import monotonic, sleep
from typing import Any


def analyze_tables(connection: Any, plan: Any, config: Any) -> list[dict[str, str]]:
    """Submit explicit statistics jobs for the native Doris tables."""
    if not config.analyze_after_load:
        return []
    return _analyze_native_tables(connection, plan, config)


def _analyze_native_tables(connection: Any, plan: Any, config: Any) -> list[dict[str, str]]:
    from .doris_layout import _FAMILIES, _family_table, _identifier

    database = _identifier(config.database)
    statements = []
    with connection.cursor() as cursor:
        prior_job_ids = _prior_job_ids(cursor, config.analyze_wait_seconds)
        for family in _FAMILIES:
            table = _family_table(plan.table, family)
            columns = _selective_columns(family) if config.statistics_policy == "selective" else ()
            column_clause = ""
            sample_clause = ""
            if columns:
                column_clause = " (" + ", ".join(_identifier(column) for column in columns) + ")"
                sample_clause = " WITH SAMPLE ROWS 4194304"
            statement = (
                f"ANALYZE TABLE {database}.{_identifier(table)}{column_clause}{sample_clause}"
            )
            cursor.execute(statement)
            statements.append(
                {
                    "table": table,
                    "statement": statement,
                    "status": "submitted",
                    "statistics_policy": config.statistics_policy,
                    "columns": ",".join(columns),
                }
            )
        lookup_table = _plan_lookup_table(plan, config)
        if lookup_table is not None:
            columns = _LOOKUP_SELECTIVE_COLUMNS if config.statistics_policy == "selective" else ()
            column_clause = ""
            sample_clause = ""
            if columns:
                column_clause = " (" + ", ".join(_identifier(column) for column in columns) + ")"
                sample_clause = " WITH SAMPLE ROWS 4194304"
            statement = (
                f"ANALYZE TABLE {database}.{_identifier(lookup_table)}"
                f"{column_clause}{sample_clause}"
            )
            cursor.execute(statement)
            statements.append(
                {
                    "table": lookup_table,
                    "statement": statement,
                    "status": "submitted",
                    "statistics_policy": config.statistics_policy,
                    "columns": ",".join(columns),
                }
            )
        return _wait_if_requested(cursor, statements, config, prior_job_ids)


def _wait_if_requested(
    cursor: Any,
    submitted: list[dict[str, str]],
    config: Any,
    prior_job_ids: set[str],
) -> list[dict[str, str]]:
    if config.analyze_wait_seconds <= 0:
        return submitted
    return _wait_for_analysis(cursor, submitted, config.analyze_wait_seconds, prior_job_ids)


def _prior_job_ids(cursor: Any, timeout: float) -> set[str]:
    if timeout <= 0:
        return set()
    return {row["job_id"] for row in _show_analysis(cursor) if isinstance(row.get("job_id"), str)}


def _wait_for_analysis(
    cursor: Any,
    submitted: list[dict[str, str]],
    timeout: float,
    prior_job_ids: set[str],
) -> list[dict[str, str]]:
    """Wait for one submitted job per table and retain Doris's status evidence."""
    deadline = monotonic() + timeout
    pending = {entry["table"] for entry in submitted}
    latest: dict[str, dict[str, str]] = {}
    while pending and monotonic() < deadline:
        pending = _poll_analysis(cursor, pending, latest, prior_job_ids)
        if pending:
            sleep(min(1.0, max(0.0, deadline - monotonic())))
    _mark_timeouts(pending, latest)
    return [latest.get(entry["table"], entry) for entry in submitted]


def _poll_analysis(
    cursor: Any,
    pending: set[str],
    latest: dict[str, dict[str, str]],
    prior_job_ids: set[str],
) -> set[str]:
    remaining = set(pending)
    for row in _show_analysis(cursor):
        candidate = _analysis_candidate(row, remaining, prior_job_ids)
        if candidate is None:
            continue
        table, evidence = candidate
        latest[table] = evidence
        if evidence["status"] in {"finished", "failed", "cancelled"}:
            remaining.remove(table)
    return remaining


def _analysis_candidate(
    row: dict[str, str], pending: set[str], prior_job_ids: set[str]
) -> tuple[str, dict[str, str]] | None:
    table = row.get("tbl_name")
    job_id = row.get("job_id")
    if not isinstance(table, str) or table not in pending:
        return None
    if not isinstance(job_id, str) or job_id in prior_job_ids:
        return None
    state = row.get("state", "unknown").upper()
    return table, {
        "table": table,
        "status": state.lower(),
        "job_id": job_id,
        "progress": row.get("progress", ""),
    }


def _mark_timeouts(pending: set[str], latest: dict[str, dict[str, str]]) -> None:
    for table in sorted(pending):
        latest[table] = {
            "table": table,
            "status": "timeout",
            "job_id": latest.get(table, {}).get("job_id", ""),
            "progress": latest.get(table, {}).get("progress", ""),
        }


def _show_analysis(cursor: Any) -> list[dict[str, str]]:
    cursor.execute("SHOW ANALYZE")
    description = cursor.description or ()
    names = [str(column[0]).lower() for column in description]
    return [
        {name: str(value) for name, value in zip(names, row, strict=False)}
        for row in cursor.fetchall()
    ]


def collect_statistics_evidence(connection: Any, plan: Any) -> dict[str, object]:
    """Capture Doris statistics views without making loading depend on them."""
    from .doris_layout import _FAMILIES, _family_table, _identifier

    database = _identifier(plan.database)
    tables: dict[str, object] = {}
    for family in _FAMILIES:
        table = _family_table(plan.table, family)
        tables[family] = {
            "table": table,
            "table_stats": _capture_rows(
                connection, f"SHOW TABLE STATS {database}.{_identifier(table)}"
            ),
            "column_stats": _capture_rows(
                connection, f"SHOW COLUMN STATS {database}.{_identifier(table)}"
            ),
            "tablet_stats": _capture_rows(
                connection, f"SHOW TABLETS FROM {database}.{_identifier(table)}"
            ),
        }
    lookup_table = _plan_lookup_table(plan, None)
    if lookup_table is not None:
        tables["name_lookup"] = {
            "table": lookup_table,
            "table_stats": _capture_rows(
                connection, f"SHOW TABLE STATS {database}.{_identifier(lookup_table)}"
            ),
            "column_stats": _capture_rows(
                connection, f"SHOW COLUMN STATS {database}.{_identifier(lookup_table)}"
            ),
            "tablet_stats": _capture_rows(
                connection, f"SHOW TABLETS FROM {database}.{_identifier(lookup_table)}"
            ),
        }
    return {
        "status": "observed"
        if all(
            isinstance(item, dict)
            and item.get("table_stats", {}).get("status") == "observed"
            and item.get("column_stats", {}).get("status") == "observed"
            and item.get("tablet_stats", {}).get("status") == "observed"
            for item in tables.values()
        )
        else "partial",
        "tables": tables,
        "show_analyze": _capture_rows(connection, "SHOW ANALYZE"),
        "show_auto_analyze": _capture_rows(connection, "SHOW AUTO ANALYZE"),
        "internal_column_statistics": _capture_rows(
            connection,
            "SELECT * FROM internal.__internal_schema.column_statistics LIMIT 10000",
        ),
    }


def _capture_rows(connection: Any, statement: str) -> dict[str, object]:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            names = [str(column[0]) for column in (cursor.description or ())]
            rows = [
                dict(zip(names, row, strict=False)) if names else list(row)
                for row in cursor.fetchall()
            ]
        return {"status": "observed", "statement": statement, "rows": rows}
    except Exception as error:  # evidence collection remains additive to the load result
        return {"status": "partial", "statement": statement, "error": str(error), "rows": []}


_SELECTIVE_COLUMN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "section": ("source_id", "section_index", "section_name"),
    "raw_chunk": ("source_id", "section_index", "chunk_index"),
    "unit": ("source_id", "unit_offset", "unit_type", "parser_status"),
    "die": (
        "source_id",
        "unit_offset",
        "die_offset",
        "ordinal",
        "parent_offset",
        "tag",
        "has_children",
        "is_null",
    ),
    "attribute": ("source_id", "unit_offset", "die_offset", "ordinal", "name", "form"),
    "reference": (
        "source_id",
        "unit_offset",
        "die_offset",
        "attribute_name",
        "relation",
        "target_offset",
        "resolution_status",
    ),
    "index": (
        "source_id",
        "unit_offset",
        "die_offset",
        "index_type",
        "name",
        "tag",
        "target_offset",
        "resolution_status",
    ),
    "range": (
        "source_id",
        "unit_offset",
        "die_offset",
        "ordinal",
        "attribute_name",
        "entry_kind",
        "parser_status",
    ),
    "location": (
        "source_id",
        "unit_offset",
        "die_offset",
        "ordinal",
        "attribute_name",
        "entry_kind",
        "parser_status",
    ),
    "line": ("source_id", "unit_offset", "ordinal", "entry_kind", "program_offset", "address"),
    "macro": ("source_id", "section_name", "record_offset", "macro_kind", "parser_status"),
    "frame": ("source_id", "section_name", "record_offset", "frame_kind", "parser_status"),
    "abbreviation": (
        "source_id",
        "unit_offset",
        "abbrev_code",
        "tag",
        "has_children",
        "parser_status",
    ),
    "name": (
        "source_id",
        "unit_offset",
        "die_offset",
        "ordinal",
        "name",
        "name_kind",
        "attribute_name",
        "parser_status",
    ),
}

_LOOKUP_SELECTIVE_COLUMNS = (
    "source_id",
    "name",
    "unit_offset",
    "die_offset",
    "index_type",
    "tag",
)


def _plan_lookup_table(plan: Any, config: Any | None) -> str | None:
    configured = plan.name_lookup_table
    if configured:
        return configured
    if plan.serving_variant_id != "canonical":
        return None
    table = plan.table
    if not table:
        return None
    if config is not None:
        return config.effective_name_lookup_table
    return f"{table}_opt_name_b8"


def _selective_columns(family: str) -> tuple[str, ...]:
    from .doris_schema import _FAMILY_COLUMNS

    candidates = _SELECTIVE_COLUMN_CANDIDATES[family]
    available = {_column_name(definition) for definition in _FAMILY_COLUMNS[family]}
    return tuple(column for column in candidates if column in available)


def _column_name(definition: str) -> str:
    return definition.split(maxsplit=1)[0].strip("`")

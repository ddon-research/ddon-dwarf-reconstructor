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
            statement = f"ANALYZE TABLE {database}.{_identifier(table)}"
            cursor.execute(statement)
            statements.append({"table": table, "statement": statement, "status": "submitted"})
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

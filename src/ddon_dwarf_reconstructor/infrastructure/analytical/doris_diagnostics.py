"""Source-bound Doris explain and query-profile evidence recording."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from .doris import DorisConfig
from .doris_diagnostics_transport import DorisDiagnosticTransport
from .doris_diagnostics_utils import (
    _aggregate_status,
    _attempts,
    _canonical_hash,
    _diagnostic_failure_status,
    _executions,
    _identifier,
    _payload_text,
    _profile_json,
    _profile_payload_summary,
    _profile_status,
    _profile_summary,
    _rows_text,
    _safe_value,
    _sha256_text,
    explain_summary,
    normalize_plan_text,
    ordered_result_sha256,
    profile_matches_query_id,
    render_sql_with_parameters,
    statement_identity,
    typed_parameter_records,
)
from .doris_layout import _FAMILIES, _family_table


class DorisDiagnosticRecorder:
    """Record explain plans and profiles without changing the measured result path."""

    def __init__(
        self,
        *,
        source_id: str,
        config: DorisConfig,
        artifact_dir: Path,
        manifest_path: Path | None = None,
        cli_path: Path | None = None,
        scope: str = "benchmark_suite",
        profile_timeout_seconds: float = 30.0,
    ) -> None:
        self.source_id = source_id
        self.config = config
        self.artifact_dir = artifact_dir.resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = None if manifest_path is None else manifest_path.resolve()
        self.scope = scope
        self._transport = DorisDiagnosticTransport(
            config, cli_path, timeout_seconds=profile_timeout_seconds
        )
        self._connection: Any | None = None
        self._schema_context: dict[str, Any] = {
            "status": "not_observed",
            "source_identity": source_id,
            "manifest_path": None if self.manifest_path is None else str(self.manifest_path),
        }
        self._statements: dict[str, dict[str, Any]] = {}
        self._errors: list[dict[str, object]] = []
        self._closed = False
        self._write_manifest()

    def attach_connection(self, connection: Any) -> None:
        """Bind a benchmark session and enable profiling on that session only."""
        self._connection = connection
        try:
            self._schema_context = self._capture_schema_context(connection)
        except Exception as error:  # schema evidence must not disable profile capture
            self._schema_context["status"] = "partial"
            self._record_error("schema_context", error)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET enable_profile = true")
            self._schema_context["session_profile_enabled"] = True
        except Exception as error:  # diagnostic failures must not alter query results
            self._schema_context["session_profile_enabled"] = False
            self._record_error("session_setup", error)
        try:
            self._schema_context["session_variables"] = self._session_variables(connection)
        except Exception as error:
            self._schema_context["session_variables"] = {"status": "partial"}
            self._record_error("session_variables", error)
        self._write_manifest()

    def prepare_statement(
        self,
        label: str,
        sql: str,
        metadata: Mapping[str, object] | None = None,
        *,
        rendered_sql: str | None = None,
        parameters: Sequence[object] = (),
    ) -> str:
        """Explain one exact SQL statement once and return its stable identity."""
        safe_sql = rendered_sql or sql
        statement_id = statement_identity(self.source_id, safe_sql)
        if statement_id in self._statements:
            return statement_id
        record: dict[str, Any] = {
            "statement_id": statement_id,
            "label": label,
            "sql": safe_sql,
            "sql_template": sql if sql != safe_sql else None,
            "sql_sha256": _sha256_text(safe_sql),
            "parameters": typed_parameter_records(parameters),
            "metadata": _safe_value(dict(metadata or {})),
            "explain": {},
            "executions": [],
        }
        self._statements[statement_id] = record
        record["explain"] = {
            "standard": self._capture_explain(statement_id, safe_sql, verbose=False),
            "verbose": self._capture_explain(statement_id, safe_sql, verbose=True),
        }
        self._write_manifest()
        return statement_id

    def capture_execution(
        self,
        statement_id: str,
        *,
        state: str,
        iteration: int,
        result_rows: Sequence[object] = (),
        result_hash: str | None = None,
        query_duration_seconds: float | None = None,
        measured_metrics: Mapping[str, object] | None = None,
        error: str | None = None,
    ) -> dict[str, object]:
        """Associate one execution with its query ID and server-side profiles."""
        record = self._statements.get(statement_id)
        if record is None:
            self._record_error("execution", ValueError(f"unknown statement: {statement_id}"))
            return {"status": "blocked", "statement_id": statement_id}
        started = perf_counter()
        query_id, query_id_error = self._last_query_id()
        execution: dict[str, object] = {
            "state": state,
            "iteration": iteration,
            "query_id": query_id,
            "ordered_result_sha256": result_hash or ordered_result_sha256(result_rows),
            "result_count": len(result_rows),
            "query_duration_seconds": query_duration_seconds,
            "measured_metrics": _safe_value(dict(measured_metrics or {})),
            "profile_status": "not_observed",
            "profile_fetch_seconds": None,
            "profile_raw": {"status": "not_observed"},
            "profile_full": {"status": "not_observed"},
            "retrieval_attempts": [],
        }
        if error is not None:
            execution["execution_error"] = error
        if query_id is None:
            execution["profile_status"] = "blocked" if query_id_error else "unavailable"
            execution["profile_error"] = query_id_error or "Doris returned no query ID"
        else:
            raw = self._capture_profile(query_id, statement_id, state, iteration, full=False)
            full = self._capture_profile(query_id, statement_id, state, iteration, full=True)
            execution["profile_raw"] = raw
            execution["profile_full"] = full
            execution["retrieval_attempts"] = [
                *_attempts(raw.get("attempts")),
                *_attempts(full.get("attempts")),
            ]
            execution["profile_status"] = _profile_status(raw, full)
            execution["profile_summary"] = _profile_summary(full, raw)
        execution["profile_fetch_seconds"] = perf_counter() - started
        execution["query_id_fetch_error"] = query_id_error
        executions = record.setdefault("executions", [])
        if isinstance(executions, list):
            executions.append(execution)
        self._write_manifest()
        return execution

    def finalize(self) -> dict[str, object]:
        """Publish the current diagnostic manifest, including partial evidence."""
        self._closed = True
        report = self._report()
        self._write_json(self.artifact_dir / "doris-diagnostics.json", report)
        return report

    def _capture_explain(self, statement_id: str, sql: str, *, verbose: bool) -> dict[str, object]:
        result = self._transport.explain(sql, verbose=verbose)
        attempts = list(result.attempts)
        text = ""
        source = result.source
        status = result.status
        error = result.error
        if result.status == "observed":
            text = _payload_text(result.payload, result.raw_text)
        else:
            fallback = self._pymysql_explain(sql, verbose=verbose)
            attempts.extend(_attempts(fallback.get("attempts")))
            if fallback.get("status") == "observed":
                text = str(fallback.get("text", ""))
                source = "pymysql"
                status = "observed"
                error = None
            elif fallback.get("error"):
                error = f"{error or result.error or 'CLI unavailable'}; {fallback['error']}"
        if not text.strip():
            return {
                "status": _diagnostic_failure_status(status),
                "source": source,
                "error": error or "EXPLAIN returned no rows",
                "attempts": attempts,
            }
        suffix = "explain-verbose" if verbose else "explain"
        root = self.artifact_dir / "statements" / statement_id
        raw_artifact = self._write_text(root / f"{suffix}.txt", text)
        normalized = normalize_plan_text(text)
        normalized_artifact = self._write_text(root / f"{suffix}.normalized.txt", normalized)
        return {
            "status": "observed",
            "source": source,
            "raw": raw_artifact,
            "normalized": normalized_artifact,
            "raw_sha256": _sha256_text(text),
            "normalized_sha256": _sha256_text(normalized),
            "summary": explain_summary(text),
            "attempts": attempts,
        }

    def _capture_profile(
        self,
        query_id: str,
        statement_id: str,
        state: str,
        iteration: int,
        *,
        full: bool,
    ) -> dict[str, object]:
        result = self._transport.profile(query_id, full=full)
        attempts = list(result.attempts)
        payload_text = _payload_text(result.payload, result.raw_text)
        if result.status != "observed" or not payload_text.strip():
            return {
                "status": _diagnostic_failure_status(result.status),
                "source": result.source,
                "error": result.error or "Doris profile was not returned",
                "attempts": attempts,
                "fetch_seconds": result.duration_seconds,
            }
        root = self.artifact_dir / "statements" / statement_id
        prefix = f"profile-{state}-{iteration:03d}-{'full' if full else 'raw'}"
        if full:
            artifact = self._write_json(
                root / f"{prefix}.json", _profile_json(result, payload_text)
            )
        else:
            artifact = self._write_text(root / f"{prefix}.txt", payload_text)
        if not profile_matches_query_id(result.payload, payload_text, query_id):
            artifact["status"] = "partial"
            artifact["accepted"] = False
            return {
                "status": "partial",
                "source": result.source,
                "requested_query_id": query_id,
                "artifact": artifact,
                "error": "FE/CLI profile did not contain the requested query ID",
                "attempts": attempts,
                "fetch_seconds": result.duration_seconds,
            }
        return {
            "status": "observed",
            "source": result.source,
            "requested_query_id": query_id,
            "artifact": artifact,
            "summary": _profile_payload_summary(result.payload, payload_text),
            "attempts": attempts,
            "fetch_seconds": result.duration_seconds,
        }

    def _pymysql_explain(self, sql: str, *, verbose: bool) -> dict[str, object]:
        if self._connection is None:
            return {"status": "unavailable", "error": "PyMySQL connection is not attached"}
        statement = f"EXPLAIN VERBOSE {sql}" if verbose else f"EXPLAIN {sql}"
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(statement)
                rows = cursor.fetchall()
            return {
                "status": "observed",
                "text": _rows_text(rows),
                "attempts": [{"source": "pymysql", "statement": statement}],
            }
        except Exception as error:  # explain evidence must not fail the result query
            return {
                "status": "partial",
                "error": str(error),
                "attempts": [{"source": "pymysql", "statement": statement, "error": str(error)}],
            }

    def _last_query_id(self) -> tuple[str | None, str | None]:
        if self._connection is None:
            return None, "PyMySQL connection is not attached"
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT last_query_id()")
                rows = cursor.fetchall()
            if not rows or not rows[0] or rows[0][0] in (None, ""):
                return None, None
            return str(rows[0][0]), None
        except Exception as error:
            return None, str(error)

    def _capture_schema_context(self, connection: Any) -> dict[str, object]:
        try:
            version = self._single_value(connection, "SELECT VERSION()")
        except Exception as error:
            version = None
            self._record_error("doris_version", error)
        tables: dict[str, object] = {}
        schema_payload: dict[str, Any] = {"version": version, "tables": {}}
        for family in _FAMILIES:
            name = _family_table(self.config.table, family)
            qualified = f"{_identifier(self.config.database)}.{_identifier(name)}"
            try:
                ddl = self._single_row(connection, f"SHOW CREATE TABLE {qualified}")
            except Exception as error:
                ddl = []
                self._record_error(f"schema_table:{family}", error)
            text = _rows_text(ddl)
            table_record: dict[str, object] = {
                "table": qualified,
                "status": "observed" if text else "partial",
                "ddl_sha256": _sha256_text(text) if text else None,
            }
            tables[family] = table_record
            schema_payload["tables"][family] = text
        snapshot = _canonical_hash(schema_payload)
        context: dict[str, object] = {
            "status": "observed"
            if all(
                isinstance(value, dict) and value.get("status") == "observed"
                for value in tables.values()
            )
            else "partial",
            "source_identity": self.source_id,
            "manifest_path": None if self.manifest_path is None else str(self.manifest_path),
            "database": self.config.database,
            "base_table": self.config.table,
            "definition_lookup_table": self.config.definition_lookup_table,
            "doris_version": version,
            "tables": tables,
            "schema_snapshot_sha256": snapshot,
        }
        self._write_json(self.artifact_dir / "schema-context.json", schema_payload)
        return context

    def _session_variables(self, connection: Any) -> dict[str, object]:
        names = (
            "enable_profile",
            "profile_level",
            "auto_profile_threshold_ms",
            "enable_sql_cache",
            "enable_query_cache",
            "exec_mem_limit",
            "parallel_pipeline_task_num",
        )
        variables: dict[str, object] = {}
        for name in names:
            try:
                rows = self._single_row(connection, f"SHOW VARIABLES LIKE '{name}'")
                if rows and rows[0]:
                    variables[name] = rows[0][-1]
            except Exception as error:
                variables[name] = {"status": "partial", "error": str(error)}
        return variables

    def _report(self) -> dict[str, object]:
        statements = list(self._statements.values())
        executions = _execution_records(statements)
        counts = _report_counts(statements, executions)
        status = _aggregate_status(self._schema_context, statements, executions, self._errors)
        return {
            "schema_version": "1.0",
            "status": status,
            "scope": self.scope,
            "source_identity": self.source_id,
            "manifest_path": None if self.manifest_path is None else str(self.manifest_path),
            "artifact_root": str(self.artifact_dir),
            "retrieval": self._transport.descriptor(),
            "schema_context": self._schema_context,
            "counts": counts,
            "statements": statements,
            "errors": self._errors,
        }

    def _single_value(self, connection: Any, sql: str) -> object | None:
        rows = self._single_row(connection, sql)
        return rows[0][0] if rows and rows[0] else None

    @staticmethod
    def _single_row(connection: Any, sql: str) -> list[tuple[Any, ...]]:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return list(cursor.fetchall())

    def _record_error(self, stage: str, error: BaseException) -> None:
        self._errors.append({"stage": stage, "type": type(error).__name__, "error": str(error)})

    def _write_manifest(self) -> None:
        try:
            self._write_json(self.artifact_dir / "doris-diagnostics.json", self._report())
        except OSError as error:
            self._record_error("artifact_write", error)

    @staticmethod
    def _write_text(path: Path, text: str) -> dict[str, object]:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256_text(text)}

    @staticmethod
    def _write_json(path: Path, payload: object) -> dict[str, object]:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        text = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2, default=str)
        temporary.write_text(text + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
        return {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256_text(text + "\n"),
        }


def _execution_records(statements: Sequence[Mapping[str, object]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for statement in statements:
        records.extend(
            item for item in _executions(statement.get("executions")) if isinstance(item, dict)
        )
    return records


def _report_counts(
    statements: Sequence[Mapping[str, object]], executions: Sequence[Mapping[str, object]]
) -> dict[str, int]:
    explain_count = _observed_explain_count(statements)
    incomplete_profiles = sum(
        item.get("profile_status") not in {"observed", "not_observed"} for item in executions
    )
    return {
        "statement_count": len(statements),
        "execution_count": len(executions),
        "profile_count": sum(item.get("profile_status") == "observed" for item in executions),
        "explain_count": explain_count,
        "explain_expected": len(statements) * 2,
        "missing_artifact_count": incomplete_profiles + len(statements) * 2 - explain_count,
    }


def _observed_explain_count(statements: Sequence[Mapping[str, object]]) -> int:
    count = 0
    for statement in statements:
        explains = statement.get("explain")
        if not isinstance(explains, dict):
            continue
        for key in ("standard", "verbose"):
            plan = explains.get(key)
            if isinstance(plan, dict) and plan.get("status") == "observed":
                count += 1
    return count


__all__ = [
    "DorisDiagnosticRecorder",
    "explain_summary",
    "normalize_plan_text",
    "ordered_result_sha256",
    "profile_matches_query_id",
    "render_sql_with_parameters",
    "statement_identity",
    "typed_parameter_records",
]

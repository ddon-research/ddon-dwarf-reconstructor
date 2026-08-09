"""Unit evidence for Doris explain and profile recording."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics import (
    DorisDiagnosticRecorder,
    normalize_plan_text,
    profile_matches_query_id,
    render_sql_with_parameters,
    statement_identity,
    typed_parameter_records,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics_transport import (
    DiagnosticTransportResult,
    DorisDiagnosticTransport,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics_utils import (
    _aggregate_status,
    _attempts,
    _diagnostic_failure_status,
    _executions,
    _payload_text,
    _profile_json,
    _profile_payload_summary,
    _profile_status,
    _profile_summary,
    _rows_text,
    _safe_value,
    _sql_literal,
    explain_summary,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Connection:
    def __init__(self) -> None:
        self.query_number = 0
        self.statements: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self)


class _Cursor:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection
        self.rows: list[tuple[object, ...]] = []
        self.description = [("value",)]

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        del params
        self.connection.statements.append(sql)
        if "last_query_id" in sql.lower():
            self.rows = [(f"query-{self.connection.query_number}",)]
        elif "version()" in sql.lower():
            self.rows = [("4.1.3-test",)]
        elif "show variables" in sql.lower():
            self.rows = [("variable", "true")]
        elif "show create table" in sql.lower():
            self.rows = [("table", "CREATE TABLE test (value INT)")]
        else:
            self.connection.query_number += 1
            self.rows = [(1,)]

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


def _explain(_self: object, sql: str, *, verbose: bool) -> DiagnosticTransportResult:
    suffix = " verbose" if verbose else ""
    return DiagnosticTransportResult("observed", "fake-cli", f"PLAN{suffix}\nTABLE scan {sql}")


def _profile(_self: object, query_id: str, *, full: bool) -> DiagnosticTransportResult:
    text = f"Query ID: {query_id}\nRows: 1\nElapsed time: 1ms"
    payload: object = {"query_id": query_id, "rows": 1} if full else text
    return DiagnosticTransportResult("observed", "fake-cli", text, payload)


def test_plan_helpers_are_stable_and_parameter_values_are_not_published() -> None:
    assert normalize_plan_text("  A\n B  C ") == "A B C"
    assert statement_identity("source", "SELECT 1") == statement_identity("source", "SELECT 1")
    assert statement_identity("source", "SELECT 1") != statement_identity("other", "SELECT 1")
    records = typed_parameter_records(("secret", 4))
    assert records[0]["type"] == "builtins.str"
    assert "secret" not in str(records)
    assert render_sql_with_parameters("SELECT %s, %s", ("safe", 4)) == "SELECT 'safe', 4"


def test_diagnostic_summary_helpers_cover_structured_and_fallback_payloads() -> None:
    plan = explain_summary(
        "TABLE `dwarf`.`full_index`\nPredicate: source_id\nCardinality: 3\nTablet: 1\nINNER JOIN"
    )
    assert plan["table_names"] == ["`dwarf`.`full_index`"]
    assert plan["contains_join"] is True

    full = {"status": "observed", "summary": {"query_id": "q1"}}
    raw = {"status": "observed", "summary": {"rows": 2}}
    assert _profile_status(raw, full) == "observed"
    assert _profile_status({"status": "blocked"}, full) == "blocked"
    assert _profile_status({"status": "unavailable"}, {"status": "unavailable"}) == "unavailable"
    assert _profile_status({"status": "partial"}, full) == "partial"
    assert _profile_summary(full, raw) == {"query_id": "q1"}
    assert _profile_summary({}, raw) == {"rows": 2}

    structured = {
        "profile": {
            "summary": {"query_id": "q1"},
            "execution_summary": {"elapsed": "1ms"},
            "changed_session_vars": {"enable_profile": "true"},
        },
        "operators": [{"name": "scan"}],
        "physical_plan": "PLAN",
    }
    summary = _profile_payload_summary(structured, "fallback")
    assert summary["operator_count"] == 1
    assert summary["physical_plan_present"] is True
    assert _profile_payload_summary({"other": True}, "Rows: 3") == {"rows": "3"}
    assert _profile_payload_summary("raw", "Rows: 3") == {"rows": "3"}
    assert _profile_json(DiagnosticTransportResult("observed", "cli", '{"x": 1}'), '{"x": 1}') == {
        "x": 1
    }
    assert _profile_json(DiagnosticTransportResult("observed", "cli", "bad"), "bad") == {
        "raw_profile": "bad"
    }

    assert _payload_text("text", "fallback") == "text"
    assert _payload_text({"text": "value"}, "fallback") == "value"
    assert _payload_text({"rows": [{"a": 1}]}, "fallback") == "1"
    assert _payload_text([(1, 2)], "fallback") == "1 | 2"
    assert _payload_text({"other": True}, "fallback") == "fallback"
    assert _rows_text([{"a": 1}, (2, 3), "value"]) == "1\n2 | 3\nvalue"
    assert _rows_text(None) == ""


def test_diagnostic_status_and_value_helpers_retain_types_without_secrets() -> None:
    assert _diagnostic_failure_status("blocked") == "blocked"
    assert _diagnostic_failure_status("unavailable") == "unavailable"
    assert _diagnostic_failure_status("unexpected") == "partial"
    assert _attempts([{"source": "cli"}, "ignored"]) == [{"source": "cli"}]
    assert _attempts("ignored") == []
    assert _executions([{"profile_status": "observed"}, "ignored"]) == [
        {"profile_status": "observed"}
    ]
    assert (
        _aggregate_status(
            {"status": "observed"}, [{"explain": {"standard": {"status": "observed"}}}], [], []
        )
        == "observed"
    )
    assert _aggregate_status({"status": "unavailable"}, [{"explain": {}}], [], []) == "unavailable"
    assert (
        _aggregate_status({"status": "observed"}, [{"explain": {}}], [], [{"error": "x"}])
        == "partial"
    )

    assert _safe_value(b"abc") == {"type": "bytes", "hex": "616263"}
    assert _safe_value({"x": [1, 2]}) == {"x": [1, 2]}
    assert _safe_value(SimpleNamespace(value=1))["type"].endswith("SimpleNamespace")
    assert _sql_literal(None) == "NULL"
    assert _sql_literal(True) == "TRUE"
    assert _sql_literal(b"ab") == "X'6162'"
    assert _sql_literal((1, "x")) == "(1, 'x')"
    assert _sql_literal("a'b\\c") == "'a''b\\\\c'"


def test_recorder_deduplicates_explains_and_profiles_every_execution(tmp_path: Path) -> None:
    connection = _Connection()
    with (
        patch.object(DorisDiagnosticTransport, "explain", _explain),
        patch.object(DorisDiagnosticTransport, "profile", _profile),
    ):
        recorder = DorisDiagnosticRecorder(
            source_id="a" * 64,
            config=DorisConfig(),
            artifact_dir=tmp_path / "diagnostics",
            cli_path=tmp_path / "missing-doriscli.exe",
        )
        recorder.attach_connection(connection)
        first = recorder.prepare_statement("lookup", "SELECT 1", {"symbol": "rLayout"})
        second = recorder.prepare_statement("lookup", "SELECT 1", {"symbol": "rLayout"})
        assert first == second
        for state, iteration in (("cold", 1), ("warm", 1), ("warm", 2)):
            recorder.capture_execution(
                first,
                state=state,
                iteration=iteration,
                result_rows=[(1,)],
            )
        report = cast(dict[str, Any], recorder.finalize())

    statement = report["statements"][0]
    assert report["status"] == "observed"
    assert report["counts"]["statement_count"] == 1
    assert report["counts"]["explain_count"] == 2
    assert report["counts"]["execution_count"] == 3
    assert report["counts"]["profile_count"] == 3
    assert all(item["profile_status"] == "observed" for item in statement["executions"])
    assert Path(statement["explain"]["verbose"]["raw"]["path"]).is_file()
    assert Path(statement["executions"][0]["profile_full"]["artifact"]["path"]).is_file()


def test_recorder_rejects_stale_profile_without_reusing_previous_query(tmp_path: Path) -> None:
    connection = _Connection()

    def stale(_self: object, _query_id: str, *, full: bool) -> DiagnosticTransportResult:
        text = "Query ID: stale-query"
        return DiagnosticTransportResult(
            "observed",
            "fake-fe",
            text,
            {"query_id": "stale-query"} if full else text,
        )

    with (
        patch.object(DorisDiagnosticTransport, "explain", _explain),
        patch.object(DorisDiagnosticTransport, "profile", stale),
    ):
        recorder = DorisDiagnosticRecorder(
            source_id="b" * 64,
            config=DorisConfig(),
            artifact_dir=tmp_path / "diagnostics",
        )
        recorder.attach_connection(connection)
        statement_id = recorder.prepare_statement("lookup", "SELECT 1")
        execution = cast(
            dict[str, Any],
            recorder.capture_execution(
                statement_id,
                state="cold",
                iteration=1,
                result_rows=[(1,)],
            ),
        )
        report = cast(dict[str, Any], recorder.finalize())

    assert execution["query_id"] == "query-1"
    assert execution["profile_status"] == "partial"
    assert execution["profile_raw"]["artifact"]["status"] == "partial"
    assert execution["profile_raw"]["artifact"]["accepted"] is False
    assert report["status"] == "partial"


def test_transport_descriptor_redacts_password_and_profile_id_matching_is_strict() -> None:
    config = DorisConfig(password="do-not-publish")
    transport = DorisDiagnosticTransport(config)
    descriptor = transport.descriptor()
    assert "do-not-publish" not in str(descriptor)
    assert profile_matches_query_id({"query_id": "q1"}, "", "q1") is True
    assert profile_matches_query_id({"query_id": "q2"}, "Query ID: q1", "q1") is False


def test_query_measurement_keeps_rows_and_profiles_each_iteration() -> None:
    from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.queries import (
        run_query_with_metrics,
    )

    diagnostics = MagicMock()
    diagnostics.prepare_statement.return_value = "statement"
    result, rows = run_query_with_metrics(
        "lookup",
        lambda: [(2,), (1,)],
        2,
        sql="SELECT 1",
        diagnostics=diagnostics,
    )

    assert rows == [(2,), (1,)]
    assert result["matches"] == 2
    assert result["diagnostic_statement_id"] == "statement"
    assert diagnostics.capture_execution.call_count == 3


def test_cli_json_capture_and_fe_profile_fallback(tmp_path: Path) -> None:
    cli = tmp_path / "doriscli.exe"
    cli.write_text("placeholder", encoding="utf-8")

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="doriscli 9.9.9", stderr="")
        if "profile" in command:
            return SimpleNamespace(returncode=1, stdout="{bad", stderr="evicted")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"rows": [{"Explain String": "PLAN FRAGMENT 0"}]}),
            stderr="",
        )

    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = b"Profile ID: query-1"
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics_transport.subprocess.run",
            run,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics_transport.urlopen",
            return_value=response,
        ),
    ):
        transport = DorisDiagnosticTransport(
            DorisConfig(password="secret"),
            cli,
        )
        explain = transport.explain("SELECT 1", verbose=True)
        profile = transport.profile("query-1", full=False)

    assert transport.cli_version == "doriscli 9.9.9"
    assert explain.status == "observed"
    assert profile.status == "observed"
    assert profile.source == "fe_http"
    assert "secret" not in str(transport.descriptor())

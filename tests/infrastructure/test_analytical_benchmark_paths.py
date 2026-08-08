"""Exercise analytical benchmark and Doris execution branches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark import _doris_measurement
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark_doris_queries import (
    doris_queries,
    doris_table_name,
    quote_doris_identifier,
    run_query_with_metrics,
    two_offsets,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import (
    DorisConfig,
    DorisLoader,
    DorisLoadPlan,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_statistics import _wait_for_analysis

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _plan(tmp_path: Path, *, analyze: bool = False) -> DorisLoadPlan:
    return DorisLoadPlan(
        database="test_db",
        table="dwarf",
        sql=("SELECT 1",),
        parquet_files=(),
        manifest_path=tmp_path / "manifest.json",
        analyze_after_load=analyze,
    )


def _connection(*, count: tuple[int, ...] | None = None) -> tuple[MagicMock, MagicMock]:
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = count
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


def test_loader_executes_native_plan_and_submits_statistics(tmp_path: Path) -> None:
    connection, cursor = _connection()
    pymysql = MagicMock(connect=MagicMock(return_value=connection))
    plan = _plan(tmp_path)
    config = DorisConfig(database="test_db", table="dwarf", analyze_after_load=True)
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris.import_optional",
            return_value=pymysql,
        ),
        patch.object(DorisLoader, "_validate_plan"),
        patch.object(DorisLoader, "_load_native_files", return_value=[{"status": "ok"}]),
    ):
        result = DorisLoader().execute(plan, config)

    assert result["status"] == "observed"
    assert len(result["analysis"]) == 14
    assert cursor.execute.call_count == 15
    connection.close.assert_called_once_with()


def test_analysis_wait_returns_finished_job_evidence() -> None:
    cursor = MagicMock()
    cursor.description = [
        ("job_id",),
        ("tbl_name",),
        ("state",),
        ("progress",),
    ]
    cursor.fetchall.return_value = [("42", "dwarf_index", "FINISHED", "20 Finished | 0 Failed")]

    result = _wait_for_analysis(
        cursor,
        [{"table": "dwarf_index", "statement": "ANALYZE TABLE", "status": "submitted"}],
        1.0,
        {"41"},
    )

    assert result == [
        {
            "table": "dwarf_index",
            "status": "finished",
            "job_id": "42",
            "progress": "20 Finished | 0 Failed",
        }
    ]


def test_loader_native_file_dispatch_is_source_family_aware(tmp_path: Path) -> None:
    parquet_file = tmp_path / "parquet" / "index" / "part-000.parquet"
    plan = DorisLoadPlan(
        "test_db",
        "dwarf",
        (),
        (parquet_file,),
        tmp_path / "manifest.json",
    )
    loader = DorisLoader()
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris._family_for_file",
            return_value="index",
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris._load_label",
            return_value="label",
        ),
        patch.object(loader, "_stream_load", return_value={"status": "ok"}) as stream_load,
    ):
        result = loader._load_native_files(plan, DorisConfig())

    assert result == [{"status": "ok"}]
    stream_load.assert_called_once_with(parquet_file, DorisConfig(), "dwarf_index", "label")


def test_loader_can_overlap_independent_native_stream_loads(tmp_path: Path) -> None:
    parquet_files = tuple(
        tmp_path / "parquet" / "index" / f"part-{index:03}.parquet" for index in range(3)
    )
    plan = DorisLoadPlan(
        "test_db",
        "dwarf",
        (),
        parquet_files,
        tmp_path / "manifest.json",
    )
    loader = DorisLoader()
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris._family_for_file",
            return_value="index",
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.doris._load_label",
            side_effect=lambda _plan, _family, path: path.name,
        ),
        patch.object(
            loader,
            "_stream_load",
            side_effect=lambda path, _config, _table, label: {"path": str(path), "label": label},
        ) as stream_load,
    ):
        result = loader._load_native_files(plan, DorisConfig(stream_load_workers=2))

    assert [entry["label"] for entry in result] == [path.name for path in parquet_files]
    assert stream_load.call_count == len(parquet_files)


def test_stream_load_follows_redirect_and_accepts_publish_timeout(tmp_path: Path) -> None:
    path = tmp_path / "part.parquet"
    path.write_bytes(b"parquet")
    redirect = MagicMock(status=307)
    redirect.getheader.return_value = "/redirect"
    redirect.read.return_value = b""
    success = MagicMock(status=200)
    success.read.return_value = b'{"Status":"Publish Timeout"}'
    first_connection = MagicMock()
    second_connection = MagicMock()
    with patch.object(
        DorisLoader,
        "_send_stream_load",
        side_effect=[(first_connection, redirect), (second_connection, success)],
    ):
        result = DorisLoader._stream_load(path, DorisConfig(), "dwarf_index", "label")

    assert result["response"] == {"Status": "Publish Timeout"}
    first_connection.close.assert_called_once_with()
    second_connection.close.assert_called_once_with()


def test_stream_load_rejects_doris_error(tmp_path: Path) -> None:
    path = tmp_path / "part.parquet"
    path.write_bytes(b"parquet")
    connection = MagicMock()
    response = MagicMock(status=400)
    response.read.return_value = b"bad request"
    with (
        patch.object(DorisLoader, "_send_stream_load", return_value=(connection, response)),
        pytest.raises(RuntimeError, match="Stream Load failed"),
    ):
        DorisLoader._stream_load(path, DorisConfig(), "dwarf_index", "label")
    connection.close.assert_called_once_with()


def test_stream_load_sender_sets_strict_parquet_headers(tmp_path: Path) -> None:
    path = tmp_path / "part.parquet"
    path.write_bytes(b"parquet")
    connection = MagicMock()
    connection.getresponse.return_value = MagicMock()
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.doris.HTTPConnection",
        return_value=connection,
    ):
        DorisLoader._send_stream_load(
            path,
            DorisConfig(database="test_db", user="root", password="secret"),
            "dwarf_index",
            "http://127.0.0.1:8040/api/test_db/dwarf_index/_stream_load?x=1",
            "label",
        )

    headers = {call.args[0]: call.args[1] for call in connection.putheader.call_args_list}
    assert headers["format"] == "parquet"
    assert headers["label"] == "label"
    assert headers["strict_mode"] == "true"
    assert headers["max_filter_ratio"] == "0"


def test_benchmark_query_helpers_cover_doris_and_empty_file_paths() -> None:
    assert two_offsets((0, 8)) == (0, 8)
    assert two_offsets((False, "8")) == (None, None)
    assert quote_doris_identifier("safe_name") == "`safe_name`"
    with pytest.raises(ValueError, match="Unsafe Doris identifier"):
        quote_doris_identifier("unsafe-name")
    measured, rows = run_query_with_metrics("query", lambda: [(1,)], 1)
    assert measured["status"] == "complete"
    assert rows == [(1,)]


def test_doris_query_suite_runs_related_queries_with_source_binding() -> None:
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    query_rows = [[(0, 10)], [(0, 10)], *[[(1,)] for _ in range(34)]]
    cursor.fetchall.side_effect = [row for rows in query_rows for row in (rows, rows)]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    pymysql = MagicMock(connect=MagicMock(return_value=connection))
    manifest = SimpleNamespace(source_identity=SimpleNamespace(sha256="a" * 64))
    config = DorisConfig(
        database="test_db", table="dwarf", definition_lookup_table="dwarf_definition_lookup"
    )
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark_doris_queries.import_optional",
            return_value=pymysql,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark_doris_queries._load_manifest_for_benchmark",
            return_value=manifest,
        ),
    ):
        measurements = doris_queries(Path("manifest.json"), config, ("Thing",), 1)

    assert len(measurements) == 18
    assert measurements[0]["symbol"] == "Thing"
    assert measurements[5]["query"] == "inheritance"
    assert measurements[6]["query"] == "field_layout"
    assert measurements[7]["query"] == "field_layout_attributes"
    assert measurements[10]["query"] == "references"
    assert measurements[-1]["query"] == "method_implementation_by_declaration"
    first_sql = cursor.execute.call_args_list[0].args[0]
    assert "`test_db`.`dwarf_definition_lookup`" in first_sql
    assert connection.close.called


def test_existing_doris_measurement_queries_without_reloading(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.DorisConfig.from_environment",
            return_value=DorisConfig(database="test_db", table="dwarf"),
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.build_doris_plan",
            return_value=_plan(tmp_path),
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.DorisLoader.execute"
        ) as execute,
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris_queries",
            return_value=[{"query": "find_definitions", "status": "complete", "matches": 1}],
        ),
    ):
        result = _doris_measurement(
            manifest,
            False,
            True,
            ("Thing",),
            1,
        )

    assert result["status"] == "observed"
    assert result["query_only"] is True
    assert result["load_status"] == "not_observed"
    assert result["queries"][0]["matches"] == 1
    execute.assert_not_called()


def test_doris_table_name_uses_native_family_tables() -> None:
    assert doris_table_name(DorisConfig(), "index") == "`dwarf`.`dwarf_records_index`"

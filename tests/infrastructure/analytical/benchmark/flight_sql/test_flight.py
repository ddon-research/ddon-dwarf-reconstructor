"""Unit coverage for the opt-in Doris Flight SQL evaluation path."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.adapter import (
    DorisFlightSqlClient,
    render_unparameterized_sql,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.hydration import (
    hydration_groups,
    hydration_specs,
    join_hydration,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.parity import (
    compare_transport_reports,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.results import (
    run_query_once,
    run_query_with_metrics,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.runner import (
    _aggregate_parity,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.smoke import (
    probe_parameter_binding,
    run_transport_smoke,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.specs import (
    ParameterizedQuery,
    contract_queries,
    definition_query,
    derived_aggregation_queries,
    field_attribute_query,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Reader:
    def __init__(self, batches: tuple[pa.RecordBatch, ...]) -> None:
        self._batches = iter(batches)

    def read_next_batch(self) -> pa.RecordBatch:
        return next(self._batches)


class _Cursor:
    def __init__(self, table: pa.Table) -> None:
        self._table = table
        self._names = tuple(field.name for field in table.schema)
        self.description = tuple((name,) for name in self._names)
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[object, ...]]:
        return [tuple(row[name] for name in self._names) for row in self._table.to_pylist()]

    def fetch_arrow_table(self) -> pa.Table:
        return self._table

    def fetch_record_batch(self) -> _Reader:
        return _Reader(tuple(self._table.to_batches(max_chunksize=1)))


class _Client:
    def __init__(self, table: pa.Table) -> None:
        self.table = table
        self.cursors: list[_Cursor] = []

    def cursor(self) -> _Cursor:
        cursor = _Cursor(self.table)
        self.cursors.append(cursor)
        return cursor

    def open(self) -> _Client:
        return self

    def close(self) -> None:
        return None

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _table() -> pa.Table:
    return pa.table(
        {
            "offset": pa.array([0, 8], type=pa.int64()),
            "large": pa.array(
                [Decimal("12345678901234567890"), None],
                type=pa.decimal128(20, 0),
            ),
            "raw": pa.array([b"die", None], type=pa.binary()),
            "day": pa.array([date(2026, 8, 9), None], type=pa.date32()),
            "when": pa.array(
                [datetime(2026, 8, 9, 12, 30), None],
                type=pa.timestamp("us"),
            ),
            "values": pa.array([[1, 2], None], type=pa.list_(pa.int64())),
            "payload": pa.array(
                [{"tag": "unit"}, None],
                type=pa.struct([("tag", pa.string())]),
            ),
        }
    )


def test_config_reads_flight_settings_without_changing_mysql_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_HOST", "be.example")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_PORT", "8050")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST", "be.example")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT", "18050")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_MAX_MESSAGE_SIZE", "33554432")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_QUERY_TIMEOUT_SECONDS", "11.5")
    monkeypatch.setenv("DDON_DORIS_FLIGHT_SQL_FETCH_TIMEOUT_SECONDS", "42")

    config = DorisConfig.from_environment()

    assert config.sql_host == "127.0.0.1"
    assert config.sql_port == 9030
    assert config.flight_sql_host == "be.example"
    assert config.flight_sql_port == 8050
    assert config.flight_sql_public_host == "be.example"
    assert config.flight_sql_public_port == 18050
    assert config.flight_sql_max_message_size == 33_554_432
    assert config.flight_sql_query_timeout_seconds == 11.5
    assert config.flight_sql_fetch_timeout_seconds == 42
    with pytest.raises(ValueError, match="flight_sql_port"):
        DorisConfig(flight_sql_port=0)


def test_parameterized_specs_keep_values_out_of_sql() -> None:
    config = DorisConfig(database="test_db", table="dwarf")
    queries = (
        definition_query(config, "source-secret", "rLayout", "?"),
        *contract_queries(config, "source-secret", 4, 8, "?"),
        field_attribute_query(config, "source-secret", 4, (8, 9), "?"),
    )

    assert queries
    assert len(contract_queries(config, "source-secret", 4, 8, "?")) + 2 == 18
    assert all("?" in query.sql and "%s" not in query.sql for query in queries)
    assert all("source-secret" not in query.sql and "rLayout" not in query.sql for query in queries)
    assert definition_query(config, "source-secret", "rLayout", "?").params == (
        "source-secret",
        "definition",
        "rLayout",
    )
    with pytest.raises(ValueError, match="Unsafe Doris identifier"):
        definition_query(DorisConfig(database="bad-name"), "source", "Thing", "?")
    aggregation_pairs = derived_aggregation_queries(config, "source-secret", 4, "?")
    assert len(aggregation_pairs) == 2
    aggregation_queries = tuple(query for pair in aggregation_pairs for query in pair)
    assert all(
        "source-secret" not in query.sql and "?" in query.sql for query in aggregation_queries
    )
    assert "SET_VAR(enable_parallel_result_sink=true)" in aggregation_pairs[0][1].sql
    assert "session_sql" not in aggregation_pairs[0][1].metadata


def test_unparameterized_renderer_escapes_supported_literals_without_repr() -> None:
    sql = render_unparameterized_sql(
        "SELECT ?, ?, ?, ?, ?, ?, ?, ?",
        (
            "O'Reilly\\dwarf",
            7,
            True,
            None,
            Decimal("123.40"),
            b"die",
            date(2026, 8, 9),
            time(12, 30),
        ),
    )

    assert sql == (
        "SELECT 'O''Reilly\\\\dwarf', 7, TRUE, NULL, 123.40, X'646965', '2026-08-09', '12:30:00'"
    )
    with pytest.raises(ValueError, match="qmark/value count mismatch"):
        render_unparameterized_sql("SELECT ?", ())
    with pytest.raises(TypeError, match="unsupported SQL literal type"):
        render_unparameterized_sql("SELECT ?", (object(),))


def test_hydration_batching_preserves_duplicate_candidate_usages() -> None:
    config = DorisConfig(database="test_db", table="dwarf")
    candidates = ((1, 10), (1, 10), (1, 11), (2, 20))

    n_plus_one = hydration_groups(candidates, "n_plus_one", 128)
    batched = hydration_groups(candidates, "batched", 2)
    specs = hydration_specs(config, "source", batched[0], "?", "die")
    joined = tuple(
        join_hydration(
            candidates,
            [((1, 10, "die"), (1, 11, "die"), (2, 20, "die"))],
            [((1, 10, "attr"), (1, 11, "attr"), (2, 20, "attr"))],
        )
    )

    assert len(n_plus_one) == 4
    assert len(batched) == 2
    assert len(specs) == 1
    assert specs[0].params == ("source", 1, 10)
    assert "die_offset = ?" in specs[0].sql
    assert len(joined) == 4
    assert joined[0][1] == joined[1][1]
    assert joined[0][2] == joined[1][2]


def test_arrow_consumption_modes_have_exact_result_digest_parity() -> None:
    table = _table()
    client = _Client(table)

    spec = ParameterizedQuery("typed", "SELECT * WHERE source_id = ?", ("source",), {})
    rows = run_query_once(client, spec, "rows")
    arrow_table = run_query_once(client, spec, "arrow_table")
    batches = run_query_once(client, spec, "record_batches")
    reduction = run_query_once(client, spec, "reduce")

    assert rows.report["result_digest"] == arrow_table.report["result_digest"]
    assert rows.report["result_digest"] == batches.report["result_digest"]
    assert rows.report["row_count"] == arrow_table.report["row_count"] == 2
    assert arrow_table.report["arrow_batch_count"] == 1
    assert batches.report["arrow_batch_count"] == 2
    assert reduction.rows == ()
    assert reduction.report["reduction"]["row_count"] == 2
    assert reduction.report["reduction"]["null_counts"]["large"] == 1

    measured = run_query_with_metrics(client, spec, "record_batches", 2)
    assert measured.report["warm_result_stable"] is True
    assert len(client.cursors) == 7

    cold = run_query_once(client, spec, "rows", "cold")
    assert cold.report["connection_mode"] == "cold"


def test_parameter_probe_blocks_without_an_unparameterized_fallback() -> None:
    class _ParameterBlockedCursor(_Cursor):
        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            if params:
                raise RuntimeError("prepared statement query is unimplemented")
            super().execute(sql, params)

    class _ParameterBlockedClient(_Client):
        def cursor(self) -> _ParameterBlockedCursor:
            cursor = _ParameterBlockedCursor(self.table)
            self.cursors.append(cursor)
            return cursor

    blocked = probe_parameter_binding(_ParameterBlockedClient(pa.table({"value": [1]})))
    assert blocked["status"] == "blocked"
    assert blocked["placeholder"] == "?"
    assert blocked["fallback"] == "none"

    smoke = run_transport_smoke(_Client(pa.table({"value": [1]})), 1)
    assert smoke["status"] == "observed"
    assert len(smoke["modes"]) == 5
    assert smoke["reused_modes"] == ("rows", "arrow_table", "record_batches", "reduce")
    assert smoke["cold_connection_modes"] == ("rows",)


def test_batch_reducer_records_derived_counts() -> None:
    table = pa.table({"tag": pa.array(["class", "class", None], type=pa.string())})
    client = _Client(table)
    spec = ParameterizedQuery(
        "tag_counts",
        "SELECT tag FROM die WHERE source_id = ?",
        ("source",),
        {"reducer": "count_by_first_column"},
    )

    result = run_query_once(client, spec, "reduce")

    assert result.report["reduction"]["counts"] == {'"class"': 2, "null": 1}
    assert (
        _aggregate_parity(
            result,
            SimpleNamespace(rows=(("class", 2), (None, 1))),
        )
        is True
    )
    measured = run_query_with_metrics(client, spec, "reduce", 1)
    assert (
        _aggregate_parity(
            measured,
            SimpleNamespace(rows=(("class", 2), (None, 1))),
        )
        is True
    )


def test_transport_parity_reports_strict_digest_mismatches() -> None:
    def query(query_name: str, result_digest: str) -> dict[str, object]:
        return {
            "query": query_name,
            "mode": "rows",
            "result_digest": result_digest,
            "matches": 1,
            "schema": ["value"],
        }

    def transport(array_digest: str) -> dict[str, object]:
        return {
            "connection_modes": ["reused"],
            "symbols": {
                "rLayout": {
                    "reused": {
                        "definition": [query("find_definitions", "same")],
                        "contract": [query("get_die", "same")],
                        "arrays": [query("array_die_1", array_digest)],
                        "hydration": [
                            {
                                "strategy": "batched",
                                "batch_size": 32,
                                "mode": "rows",
                                "result_digest": "same",
                            }
                        ],
                    }
                }
            },
        }

    report = compare_transport_reports(transport("mysql"), transport("flight"))

    assert report["status"] == "partial"
    assert report["compared"] == 4
    assert report["matched"] == 3
    assert report["mismatched"] == 1
    array_report = next(item for item in report["categories"] if item["category"] == "arrays")
    assert array_report["mismatches"][0]["key"] == "array_die_1"


def test_flight_client_sets_message_and_timeout_options_and_reuses_connection() -> None:
    manager = SimpleNamespace(
        DatabaseOptions=SimpleNamespace(
            USERNAME=SimpleNamespace(value="username"),
            PASSWORD=SimpleNamespace(value="password"),
        )
    )
    flight = SimpleNamespace(
        DatabaseOptions=SimpleNamespace(
            WITH_MAX_MSG_SIZE=SimpleNamespace(value="max_message"),
        ),
        ConnectionOptions=SimpleNamespace(
            TIMEOUT_QUERY=SimpleNamespace(value="query_timeout"),
            TIMEOUT_FETCH=SimpleNamespace(value="fetch_timeout"),
        ),
    )
    connection = MagicMock()
    dbapi = SimpleNamespace(connect=MagicMock(return_value=connection))
    imports = {
        "adbc_driver_manager": manager,
        "adbc_driver_flightsql": flight,
        "adbc_driver_flightsql.dbapi": dbapi,
    }
    config = DorisConfig(
        user="root",
        password="secret",
        flight_sql_host="fe.example",
        flight_sql_port=8070,
        flight_sql_max_message_size=32,
        flight_sql_query_timeout_seconds=3.0,
        flight_sql_fetch_timeout_seconds=7.0,
    )

    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.adapter.import_optional",
            side_effect=lambda name, _extra: imports[name],
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.adapter._package_versions",
            return_value={"adbc-driver-manager": "1.12.0"},
        ),
    ):
        client = DorisFlightSqlClient(config)
        assert client.open() is client
        assert client.open() is client

    dbapi.connect.assert_called_once_with(
        uri="grpc://fe.example:8070",
        db_kwargs={"username": "root", "password": "secret", "max_message": "32"},
        autocommit=True,
    )
    connection.adbc_connection.set_options.assert_called_once_with(
        query_timeout=3.0,
        fetch_timeout=7.0,
    )
    client.close()
    connection.close.assert_called_once_with()


def test_flight_client_fallback_reconnects_and_sends_complete_sql() -> None:
    manager = SimpleNamespace(
        DatabaseOptions=SimpleNamespace(
            USERNAME=SimpleNamespace(value="username"),
            PASSWORD=SimpleNamespace(value="password"),
        )
    )
    flight = SimpleNamespace(
        DatabaseOptions=SimpleNamespace(
            WITH_MAX_MSG_SIZE=SimpleNamespace(value="max_message"),
        ),
        ConnectionOptions=SimpleNamespace(
            TIMEOUT_QUERY=SimpleNamespace(value="query_timeout"),
            TIMEOUT_FETCH=SimpleNamespace(value="fetch_timeout"),
        ),
    )
    connection = MagicMock()
    cursor = _Cursor(pa.table({"value": [1]}))
    connection.cursor.return_value = cursor
    dbapi = SimpleNamespace(connect=MagicMock(return_value=connection))
    imports = {
        "adbc_driver_manager": manager,
        "adbc_driver_flightsql": flight,
        "adbc_driver_flightsql.dbapi": dbapi,
    }

    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.adapter.import_optional",
            side_effect=lambda name, _extra: imports[name],
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.adapter._package_versions",
            return_value={},
        ),
    ):
        client = DorisFlightSqlClient(DorisConfig())
        client.open()
        client.enable_unparameterized_fallback()
        with client.cursor() as fallback_cursor:
            fallback_cursor.execute("SELECT ? AS value", ("O'Reilly",))

    assert client.execution_mode == "unparameterized_fallback"
    assert cursor.executed == [("SELECT 'O''Reilly' AS value", ())]
    assert dbapi.connect.call_count == 2

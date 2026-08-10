"""Opt-in MySQL versus Arrow Flight SQL benchmark for native Doris."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from .....domain.models.analytical_dwarf import MaterializationManifest
from ...doris import DorisConfig
from ...doris_layout import _FAMILIES
from ...manifest import load_manifest
from ...optional import AnalyticalDependencyError, import_optional
from .adapter import DorisFlightSqlClient, FlightSqlCursor
from .hydration import (
    hydration_groups,
    hydration_specs,
    join_hydration,
    qualified_table,
)
from .parity import compare_transport_reports
from .results import (
    ConnectionMode,
    FetchMode,
    QueryClient,
    digest,
    run_query_once,
    run_query_with_metrics,
)
from .smoke import probe_parameter_binding, run_transport_smoke
from .specs import (
    ParameterizedQuery,
    contract_queries,
    definition_query,
    derived_aggregation_queries,
    field_attribute_query,
)


class _MySqlClient:
    """Small PyMySQL adapter used only as the row-oriented comparison path."""

    def __init__(self, config: DorisConfig) -> None:
        self._config = config
        self._connection: Any = None

    def open(self) -> _MySqlClient:
        pymysql = import_optional("pymysql", "analytical")
        self._connection = pymysql.connect(
            host=self._config.sql_host,
            port=self._config.sql_port,
            user=self._config.user,
            password=self._config.password,
            database=self._config.database,
            autocommit=True,
        )
        return self

    def cursor(self) -> FlightSqlCursor:
        if self._connection is None:
            raise RuntimeError("MySQL benchmark client is not open")
        return self._connection.cursor()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> _MySqlClient:
        return self.open()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def run_doris_flight_benchmark(
    manifest_path: Path,
    output_dir: Path,
    *,
    config: DorisConfig | None = None,
    symbols: tuple[str, ...] = ("MtObject", "rLayout"),
    iterations: int = 3,
    include_mysql: bool = True,
    allow_unparameterized_fallback: bool = False,
    include_cold_connections: bool = True,
) -> dict[str, Any]:
    """Run the explicit transport, Arrow-consumption, and hydration matrix."""
    if iterations < 1:
        raise ValueError("iterations must be positive")
    connection_modes: tuple[ConnectionMode, ...] = (
        ("reused", "cold") if include_cold_connections else ("reused",)
    )
    manifest = load_manifest(manifest_path)
    config = config or DorisConfig.from_environment()
    report = _base_report(manifest_path, manifest, config, symbols, iterations)
    report["benchmark_options"] = {
        "allow_unparameterized_fallback": allow_unparameterized_fallback,
        "connection_modes": connection_modes,
    }
    if manifest.status != "complete":
        report["status"] = "blocked"
        report["reason"] = "Flight SQL comparison requires a complete source-bound manifest."
        return _publish_report(output_dir, report)

    if include_mysql:
        report["mysql"] = _run_mysql_transport(
            config, manifest, symbols, iterations, connection_modes
        )
    report["flight_sql"] = _run_flight_transport(
        config,
        manifest,
        symbols,
        iterations,
        connection_modes,
        allow_unparameterized_fallback,
    )
    _add_transport_parity(report, include_mysql)
    report["status"] = _overall_status(report)
    return _publish_report(output_dir, report)


def _run_mysql_transport(
    config: DorisConfig,
    manifest: MaterializationManifest,
    symbols: tuple[str, ...],
    iterations: int,
    connection_modes: tuple[ConnectionMode, ...],
) -> dict[str, Any]:
    return _run_transport(
        _MySqlClient(config),
        config,
        manifest,
        symbols,
        iterations,
        "%s",
        ("rows",),
        connection_modes=connection_modes,
    )


def _run_flight_transport(
    config: DorisConfig,
    manifest: MaterializationManifest,
    symbols: tuple[str, ...],
    iterations: int,
    connection_modes: tuple[ConnectionMode, ...],
    allow_unparameterized_fallback: bool,
) -> dict[str, Any]:
    try:
        return _run_transport(
            DorisFlightSqlClient(config),
            config,
            manifest,
            symbols,
            iterations,
            "?",
            ("rows", "arrow_table", "record_batches", "reduce"),
            connection_modes=connection_modes,
            allow_unparameterized_fallback=allow_unparameterized_fallback,
        )
    except AnalyticalDependencyError as error:
        return {"status": "unavailable", "reason": str(error)}
    except Exception as error:
        return {"status": "blocked", "reason": f"{type(error).__name__}: {error}"}


def _add_transport_parity(report: dict[str, Any], include_mysql: bool) -> None:
    if include_mysql and "mysql" in report and "flight_sql" in report:
        report["transport_parity"] = compare_transport_reports(
            report["mysql"], report["flight_sql"]
        )


def _run_transport(
    client: QueryClient,
    config: DorisConfig,
    manifest: MaterializationManifest,
    symbols: tuple[str, ...],
    iterations: int,
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    *,
    connection_modes: tuple[ConnectionMode, ...] = ("reused", "cold"),
    allow_unparameterized_fallback: bool = False,
) -> dict[str, Any]:
    try:
        with client as opened:
            transport: dict[str, Any] = {
                "status": "observed",
                "placeholder": placeholder,
                "modes": modes,
                "connection_modes": connection_modes,
                "execution_mode": "qmark" if placeholder == "?" else "mysql_parameterized",
                "server_evidence": {
                    "status": "not_observed",
                    "scanned_rows": None,
                    "scanned_bytes": None,
                    "tablet_count": None,
                    "be_memory_bytes": None,
                    "query_profiles": (),
                    "source": "Doris profile/EXPLAIN evidence is collected separately.",
                },
                "symbols": {},
            }
            if isinstance(opened, DorisFlightSqlClient):
                transport["endpoint"] = opened.endpoint
                transport["driver_versions"] = opened.driver_versions
                parameter_binding = probe_parameter_binding(opened)
                transport["parameter_binding"] = parameter_binding
                if parameter_binding["status"] != "observed":
                    if not allow_unparameterized_fallback:
                        transport["status"] = "blocked"
                        transport["reason"] = (
                            "Doris/Flight SQL does not support the required qmark parameter "
                            "protocol; no unparameterized SQL fallback was used."
                        )
                        transport["transport_smoke"] = run_transport_smoke(opened, iterations)
                        return transport
                    opened.enable_unparameterized_fallback()
                    transport["status"] = "partial"
                    transport["execution_mode"] = opened.execution_mode
                    transport["fallback"] = {
                        "status": "observed",
                        "mode": opened.execution_mode,
                        "reason": (
                            "Doris Flight producer rejects acceptPutPreparedStatementQuery; "
                            "qmark values were rendered as checked SQL literals."
                        ),
                    }
            for symbol in symbols:
                transport["symbols"][symbol] = {
                    connection_mode: _run_symbol(
                        opened,
                        config,
                        manifest.source_identity.sha256,
                        symbol,
                        iterations,
                        placeholder,
                        modes,
                        connection_mode,
                    )
                    for connection_mode in connection_modes
                }
            return transport
    except AnalyticalDependencyError:
        raise
    except Exception as error:
        return {"status": "blocked", "reason": f"{type(error).__name__}: {error}"}


def _run_symbol(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    symbol: str,
    iterations: int,
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    connection_mode: ConnectionMode,
) -> dict[str, Any]:
    definition = definition_query(config, source_id, symbol, placeholder)
    definition_runs = {
        mode: run_query_with_metrics(client, definition, mode, iterations, connection_mode)
        for mode in modes
    }
    rows_run = definition_runs["rows"]
    offsets = _first_offsets(rows_run.rows)
    result: dict[str, Any] = {
        "definition": [run.report for run in definition_runs.values()],
        "contract": [],
        "arrays": [],
        "aggregations": [],
        "hydration": [],
    }
    if offsets is None:
        return result

    unit_offset, die_offset = offsets
    result["contract"] = _run_contract(
        client,
        config,
        source_id,
        unit_offset,
        die_offset,
        placeholder,
        modes,
        iterations,
        connection_mode,
    )
    result["arrays"] = _run_arrays(
        client, config, source_id, unit_offset, placeholder, modes, iterations, connection_mode
    )
    result["aggregations"] = _run_aggregations(
        client, config, source_id, unit_offset, placeholder, modes, iterations, connection_mode
    )
    result["hydration"] = _run_hydration_matrix(
        client, config, source_id, rows_run.rows, placeholder, modes, connection_mode
    )
    return result


def _run_contract(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    die_offset: int,
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    iterations: int,
    connection_mode: ConnectionMode,
) -> list[dict[str, Any]]:
    specs = contract_queries(config, source_id, unit_offset, die_offset, placeholder)
    field_offsets: tuple[int, ...] = ()
    reports: list[dict[str, Any]] = []
    for spec in specs:
        runs = {
            mode: run_query_with_metrics(client, spec, mode, iterations, connection_mode)
            for mode in modes
        }
        reports.extend(run.report for run in runs.values())
        if spec.name == "field_layout":
            field_offsets = _die_offsets(runs["rows"].rows)
    field_spec = field_attribute_query(config, source_id, unit_offset, field_offsets, placeholder)
    reports.extend(
        run_query_with_metrics(client, field_spec, mode, iterations, connection_mode).report
        for mode in modes
    )
    return reports


def _run_arrays(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    iterations: int,
    connection_mode: ConnectionMode,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for limit in (1, 8, 64, 256, 1024, 10_000):
        for spec in _array_queries(config, source_id, unit_offset, placeholder, limit):
            reports.extend(
                run_query_with_metrics(client, spec, mode, iterations, connection_mode).report
                for mode in modes
            )
    return reports


def _run_hydration_matrix(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    candidates: tuple[tuple[Any, ...], ...],
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    connection_mode: ConnectionMode,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for batch_size in (32, 128, 512, 2_048):
        for strategy in ("n_plus_one", "batched"):
            reports.extend(
                _run_hydration(
                    client,
                    config,
                    source_id,
                    candidates,
                    placeholder,
                    strategy,
                    batch_size,
                    modes,
                    connection_mode,
                )
            )
    return reports


def _run_aggregations(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    placeholder: Literal["%s", "?"],
    modes: tuple[FetchMode, ...],
    iterations: int,
    connection_mode: ConnectionMode,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for client_spec, server_spec in derived_aggregation_queries(
        config, source_id, unit_offset, placeholder
    ):
        client_runs = {
            mode: run_query_with_metrics(client, client_spec, mode, iterations, connection_mode)
            for mode in modes
        }
        server_modes = tuple(mode for mode in modes if mode != "reduce")
        server_runs = {
            mode: run_query_with_metrics(client, server_spec, mode, iterations, connection_mode)
            for mode in server_modes
        }
        reports.append(
            {
                "aggregation": client_spec.metadata["aggregation"],
                "connection_mode": connection_mode,
                "client_parallel_result_sink": client_spec.metadata["parallel_result_sink"],
                "doris_parallel_result_sink": server_spec.metadata["parallel_result_sink"],
                "client_reduction": client_runs.get("reduce").report
                if "reduce" in client_runs
                else None,
                "client_vs_doris_exact": _aggregate_parity(
                    client_runs.get("reduce"), server_runs.get("rows")
                ),
                "client": [run.report for run in client_runs.values()],
                "doris": [run.report for run in server_runs.values()],
            }
        )
    return reports


def _aggregate_parity(client_run: Any, server_run: Any) -> bool | None:
    if client_run is None or server_run is None:
        return None
    reduction = client_run.report.get("reduction")
    if not isinstance(reduction, dict):
        cold_report = client_run.report.get("cold", {})
        reduction = cold_report.get("reduction", {}) if isinstance(cold_report, dict) else {}
    client_counts = reduction.get("counts")
    if not isinstance(client_counts, dict):
        return None
    server_counts: dict[str, int] = {}
    for row in server_run.rows:
        if len(row) >= 2:
            key = json.dumps(row[0], sort_keys=True, ensure_ascii=True, default=str)
            server_counts[key] = int(row[1])
    return client_counts == server_counts


def _array_queries(
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    placeholder: Literal["%s", "?"],
    limit: int,
) -> tuple[ParameterizedQuery, ...]:
    tables = {family: qualified_table(config, family) for family in _FAMILIES}
    queries: list[ParameterizedQuery] = []
    for family, order in (("die", "ordinal"), ("attribute", "die_offset, ordinal")):
        if family not in tables:
            continue
        queries.append(
            ParameterizedQuery(
                f"array_{family}_{limit}",
                f"SELECT * FROM {tables[family]} WHERE source_id = {placeholder} "
                f"AND unit_offset = {placeholder} ORDER BY {order} LIMIT {limit}",
                (source_id, unit_offset),
                {"unit_offset": unit_offset, "limit": limit, "family": family},
            )
        )
    return tuple(queries)


def _run_hydration(
    client: QueryClient,
    config: DorisConfig,
    source_id: str,
    candidates: tuple[tuple[Any, ...], ...],
    placeholder: Literal["%s", "?"],
    strategy: str,
    batch_size: int,
    modes: tuple[FetchMode, ...],
    connection_mode: ConnectionMode,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if not candidates:
        return reports
    for mode in modes:
        if mode not in ("rows", "record_batches"):
            continue
        started = perf_counter()
        outputs: list[dict[str, Any]] = []
        query_count = 0
        for group in hydration_groups(candidates, strategy, batch_size):
            die_specs = hydration_specs(config, source_id, group, placeholder, "die")
            attr_specs = hydration_specs(config, source_id, group, placeholder, "attribute")
            die_rows = [
                run_query_once(client, spec, mode, connection_mode).rows for spec in die_specs
            ]
            attr_rows = [
                run_query_once(client, spec, mode, connection_mode).rows for spec in attr_specs
            ]
            query_count += len(die_specs) + len(attr_specs)
            outputs.extend(
                {"candidate": index, "die": die, "attributes": attrs}
                for index, die, attrs in join_hydration(group, die_rows, attr_rows)
            )
        reports.append(
            {
                "query": "definition_hydration",
                "mode": mode,
                "connection_mode": connection_mode,
                "strategy": strategy,
                "batch_size": batch_size,
                "candidate_count": len(candidates),
                "query_count": query_count,
                "wall_seconds": perf_counter() - started,
                "result_digest": digest(outputs),
            }
        )
    return reports


def _first_offsets(rows: tuple[tuple[Any, ...], ...]) -> tuple[int, int] | None:
    if not rows or len(rows[0]) < 2:
        return None
    values = rows[0][:2]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return None
    return values[0], values[1]


def _die_offsets(rows: tuple[tuple[Any, ...], ...]) -> tuple[int, ...]:
    return tuple(
        row[0] for row in rows if row and isinstance(row[0], int) and not isinstance(row[0], bool)
    )


def _base_report(
    manifest_path: Path,
    manifest: MaterializationManifest,
    config: DorisConfig,
    symbols: tuple[str, ...],
    iterations: int,
) -> dict[str, Any]:
    return {
        "status": "not_observed",
        "manifest": str(manifest_path.resolve()),
        "source_id": manifest.source_identity.sha256,
        "manifest_status": manifest.status,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "symbols": symbols,
        "iterations": iterations,
        "server_cache": {
            "cold": "not_observed",
            "warm": "not_observed",
            "note": "Cold-server state requires an explicit Doris service restart or cache-control run.",
        },
        "config": {
            "database": config.database,
            "table": config.table,
            "sql_host": config.sql_host,
            "sql_port": config.sql_port,
            "flight_sql_host": config.flight_sql_host,
            "flight_sql_port": config.flight_sql_port,
            "flight_sql_uri": config.flight_sql_uri,
            "flight_sql_fe_public_host": config.flight_sql_fe_public_host,
            "flight_sql_public_host": config.flight_sql_public_host,
            "flight_sql_public_port": config.flight_sql_public_port,
            "flight_sql_max_message_size": config.flight_sql_max_message_size,
            "flight_sql_query_timeout_seconds": config.flight_sql_query_timeout_seconds,
            "flight_sql_fetch_timeout_seconds": config.flight_sql_fetch_timeout_seconds,
        },
        "server_evidence": {
            "status": "not_observed",
            "scanned_rows": None,
            "scanned_bytes": None,
            "tablet_count": None,
            "be_memory_bytes": None,
            "query_profiles": (),
            "source": "Doris profile/EXPLAIN evidence is collected separately.",
        },
    }


def _overall_status(report: dict[str, Any]) -> str:
    flight = report.get("flight_sql", {})
    return str(flight.get("status", "not_observed"))


def _publish_report(output_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "doris-flight-report.json"
    temporary = target.with_suffix(".partial")
    report["report_path"] = str(target.resolve())
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(target)
    return report

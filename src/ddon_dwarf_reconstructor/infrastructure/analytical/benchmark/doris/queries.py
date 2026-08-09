"""Native-Doris query measurements for the analytical store contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .....domain.models.analytical_dwarf import MaterializationManifest
from ...doris import DorisConfig
from ...doris_diagnostics import DorisDiagnosticRecorder, ordered_result_sha256
from ...doris_layout import _FAMILIES
from ...manifest import load_manifest
from ...optional import import_optional
from ..common.metrics import distribution, measure


def doris_queries(
    manifest_path: Path,
    config: DorisConfig,
    symbols: tuple[str, ...],
    iterations: int,
    diagnostics: DorisDiagnosticRecorder | None = None,
) -> list[dict[str, Any]]:
    """Run the bounded correctness and coverage suite against native Doris tables."""
    pymysql = import_optional("pymysql", "analytical")
    source_id = _load_manifest_for_benchmark(manifest_path).source_identity.sha256
    connection = pymysql.connect(
        host=config.sql_host,
        port=config.sql_port,
        user=config.user,
        password=config.password,
        autocommit=True,
    )
    try:
        if diagnostics is not None:
            diagnostics.attach_connection(connection)
        return _doris_symbol_queries(
            connection, config, source_id, symbols, iterations, diagnostics=diagnostics
        )
    finally:
        if diagnostics is not None:
            diagnostics.finalize()
        connection.close()


def _doris_symbol_queries(
    connection: Any,
    config: DorisConfig,
    source_id: str,
    symbols: tuple[str, ...],
    iterations: int,
    *,
    diagnostics: DorisDiagnosticRecorder | None = None,
) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        tables = {family: doris_table_name(config, family) for family in _FAMILIES}

        def run(sql: str) -> list[tuple[Any, ...]]:
            cursor.execute(sql)
            return list(cursor.fetchall())

        measurements: list[dict[str, Any]] = []
        definition_table = _lookup_table(config, tables["index"], config.definition_lookup_table)
        method_table = _lookup_table(config, tables["index"], config.method_lookup_table)
        if config.die_lookup_table is not None:
            tables["die"] = _lookup_table(config, tables["die"], config.die_lookup_table)
        for symbol in symbols:
            rows, measurement = _doris_definition_query(
                definition_table,
                source_id,
                symbol,
                run,
                iterations,
                diagnostics=diagnostics,
            )
            measurements.append(measurement)
            if rows:
                unit_offset, die_offset = two_offsets(rows[0])
                if unit_offset is not None and die_offset is not None:
                    measurements.extend(
                        _doris_related_queries(
                            tables,
                            source_id,
                            unit_offset,
                            die_offset,
                            run,
                            iterations,
                            method_table=method_table,
                            diagnostics=diagnostics,
                        )
                    )
        return measurements


def _lookup_table(config: DorisConfig, default: str, configured: str | None) -> str:
    """Return an optional native serving projection for one lookup family."""
    if configured is None:
        return default
    return f"{quote_doris_identifier(config.database)}.{quote_doris_identifier(configured)}"


def _doris_definition_query(
    table: str,
    source_id: str,
    symbol: str,
    run: Callable[[str], list[tuple[Any, ...]]],
    iterations: int,
    *,
    diagnostics: DorisDiagnosticRecorder | None = None,
) -> tuple[list[tuple[Any, ...]], dict[str, Any]]:
    escaped_symbol = sql_literal_for_benchmark(symbol)
    sql = (
        f"SELECT unit_offset, die_offset FROM {table} WHERE source_id = '{source_id}' "
        "AND index_type = 'definition' AND name = "
        f"'{escaped_symbol}' ORDER BY unit_offset, die_offset LIMIT 1001"
    )
    measurement, rows = run_query_with_metrics(
        "find_definitions",
        lambda: run(sql),
        iterations,
        sql=sql,
        diagnostics=diagnostics,
        symbol=symbol,
    )
    return rows, measurement


def _doris_related_queries(
    tables: dict[str, str],
    source_id: str,
    unit_offset: int,
    die_offset: int,
    run: Callable[[str], list[tuple[Any, ...]]],
    iterations: int,
    *,
    method_table: str,
    diagnostics: DorisDiagnosticRecorder | None = None,
) -> list[dict[str, Any]]:
    measurements: list[dict[str, Any]] = []
    field_rows: list[tuple[Any, ...]] = []
    for name, sql, metadata in _doris_query_specs(
        tables, source_id, unit_offset, die_offset, method_table=method_table
    ):
        measurement, rows = run_query_with_metrics(
            name,
            lambda sql=sql: run(sql),
            iterations,
            sql=sql,
            diagnostics=diagnostics,
            **metadata,
        )
        measurements.append(measurement)
        if name == "field_layout":
            field_rows = rows
    if "attribute" in tables:
        measurement, _rows = run_query_with_metrics(
            "field_layout_attributes",
            lambda: run(
                _field_layout_attribute_sql(tables["attribute"], source_id, unit_offset, field_rows)
            ),
            iterations,
            sql=_field_layout_attribute_sql(
                tables["attribute"], source_id, unit_offset, field_rows
            ),
            diagnostics=diagnostics,
            unit_offset=unit_offset,
            die_offset=die_offset,
        )
        field_index = next(
            (index for index, item in enumerate(measurements) if item["query"] == "field_layout"),
            len(measurements) - 1,
        )
        measurements.insert(field_index + 1, measurement)
    return measurements


def _field_layout_attribute_sql(
    table: str,
    source_id: str,
    unit_offset: int,
    field_rows: list[tuple[Any, ...]],
) -> str:
    offsets = tuple(
        sorted(
            {
                value
                for row in field_rows
                if row and isinstance((value := row[0]), int) and not isinstance(value, bool)
            }
        )[:1000]
    )
    offset_sql = ", ".join(str(value) for value in offsets) or "-1"
    return (
        f"SELECT die_offset, name, decoded_value_kind, decoded_value_int, decoded_value_uint, "
        f"decoded_value_text FROM {table} WHERE source_id = '{source_id}' "
        f"AND unit_offset = {unit_offset} AND die_offset IN ({offset_sql}) "
        "AND name IN ('DW_AT_data_member_location', 'DW_AT_byte_size', 'DW_AT_bit_size', "
        "'DW_AT_bit_offset', 'DW_AT_type', 'DW_AT_upper_bound', 'DW_AT_count', "
        "'DW_AT_lower_bound', 'DW_AT_declaration') ORDER BY die_offset, ordinal LIMIT 1001"
    )


def _doris_query_specs(
    tables: dict[str, str],
    source_id: str,
    unit_offset: int,
    die_offset: int,
    *,
    method_table: str,
) -> tuple[tuple[str, str, dict[str, int]], ...]:
    source = f"source_id = '{source_id}'"
    unit = f"{source} AND unit_offset = {unit_offset}"
    die_key = f"{unit} AND die_offset = {die_offset}"
    specs = _unit_and_hierarchy_specs(tables, unit, die_key, unit_offset, die_offset)
    specs += _attribute_and_reference_specs(tables, die_key, unit_offset, die_offset)
    specs += _source_evidence_specs(tables, source, unit, die_key, unit_offset, die_offset)
    specs += _method_specs(method_table, source, die_offset)
    return tuple(specs)


QuerySpec = tuple[str, str, dict[str, int]]


def _add_query_spec(
    specs: list[QuerySpec],
    tables: dict[str, str],
    name: str,
    family: str,
    sql: str,
    metadata: dict[str, int],
) -> None:
    if family in tables:
        specs.append((name, sql, metadata))


def _unit_and_hierarchy_specs(
    tables: dict[str, str],
    unit: str,
    die_key: str,
    unit_offset: int,
    die_offset: int,
) -> list[QuerySpec]:
    specs: list[QuerySpec] = []
    die_metadata = {"unit_offset": unit_offset, "die_offset": die_offset}
    _add_query_spec(
        specs,
        tables,
        "get_compilation_unit",
        "unit",
        f"SELECT unit_offset FROM {tables.get('unit', '')} WHERE {unit} LIMIT 1001",
        {"unit_offset": unit_offset},
    )
    _add_query_spec(
        specs,
        tables,
        "get_die",
        "die",
        f"SELECT die_offset, tag, parent_offset FROM {tables.get('die', '')} "
        f"WHERE {die_key} LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "parent",
        "die",
        f"SELECT parent_offset FROM {tables.get('die', '')} WHERE {die_key} "
        "AND parent_offset IS NOT NULL LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "children",
        "die",
        f"SELECT die_offset FROM {tables.get('die', '')} WHERE {unit} "
        f"AND parent_offset = {die_offset} ORDER BY ordinal LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "inheritance",
        "die",
        f"SELECT die_offset FROM {tables.get('die', '')} WHERE {unit} "
        f"AND parent_offset = {die_offset} AND tag = 'DW_TAG_inheritance' "
        "ORDER BY ordinal LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "field_layout",
        "die",
        f"SELECT die_offset FROM {tables.get('die', '')} WHERE {unit} "
        f"AND parent_offset = {die_offset} AND tag = 'DW_TAG_member' "
        "ORDER BY ordinal LIMIT 1001",
        die_metadata,
    )
    return specs


def _attribute_and_reference_specs(
    tables: dict[str, str],
    die_key: str,
    unit_offset: int,
    die_offset: int,
) -> list[QuerySpec]:
    specs: list[QuerySpec] = []
    metadata = {"unit_offset": unit_offset, "die_offset": die_offset}
    _add_query_spec(
        specs,
        tables,
        "type_and_declarator_attributes",
        "attribute",
        f"SELECT name, decoded_value_kind, decoded_value_int, decoded_value_uint, "
        f"decoded_value_text, decoded_value_json FROM {tables.get('attribute', '')} "
        f"WHERE {die_key} AND name IN ('DW_AT_type', 'DW_AT_byte_size', 'DW_AT_encoding', "
        "'DW_AT_data_member_location', 'DW_AT_upper_bound', 'DW_AT_count', "
        "'DW_AT_lower_bound', 'DW_AT_declaration', 'DW_AT_const_value') "
        "ORDER BY ordinal LIMIT 1001",
        metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "name_occurrences",
        "name",
        f"SELECT name, name_kind, attribute_name FROM {tables.get('name', '')} "
        f"WHERE {die_key} ORDER BY ordinal LIMIT 1001",
        metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "references",
        "reference",
        f"SELECT attribute_name, relation, target_offset, resolution_status "
        f"FROM {tables.get('reference', '')} WHERE {die_key} "
        "ORDER BY attribute_name LIMIT 1001",
        metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "type_reference_resolution",
        "reference",
        f"SELECT attribute_name, target_offset, resolution_status FROM {tables.get('reference', '')} "
        f"WHERE {die_key} AND relation <> 'parent' ORDER BY attribute_name LIMIT 1001",
        metadata,
    )
    return specs


def _source_evidence_specs(
    tables: dict[str, str],
    source: str,
    unit: str,
    die_key: str,
    unit_offset: int,
    die_offset: int,
) -> list[QuerySpec]:
    specs: list[QuerySpec] = []
    die_metadata = {"unit_offset": unit_offset, "die_offset": die_offset}
    unit_metadata = {"unit_offset": unit_offset}
    _add_query_spec(
        specs,
        tables,
        "global_die_offset",
        "die",
        f"SELECT unit_offset, die_offset, tag, parent_offset FROM {tables.get('die', '')} "
        f"WHERE {source} AND die_offset = {die_offset} ORDER BY unit_offset LIMIT 1001",
        {"die_offset": die_offset},
    )
    _add_query_spec(
        specs,
        tables,
        "ranges",
        "range",
        f"SELECT ordinal, start_address, end_address, parser_status FROM {tables.get('range', '')} "
        f"WHERE {die_key} ORDER BY ordinal LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "locations",
        "location",
        f"SELECT ordinal, start_address, end_address, expression_json "
        f"FROM {tables.get('location', '')} WHERE {die_key} ORDER BY ordinal LIMIT 1001",
        die_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "line_files",
        "line",
        f"SELECT ordinal, entry_kind, source_file, directory, file_index, directory_index, "
        f"line, address "
        f"FROM {tables.get('line', '')} WHERE {unit} "
        f"ORDER BY entry_kind, ordinal LIMIT 1001",
        unit_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "source_provenance",
        "section",
        f"SELECT section_index, section_name, raw_path, raw_sha256 FROM {tables.get('section', '')} "
        f"WHERE {source} ORDER BY section_index LIMIT 1001",
        unit_metadata,
    )
    _add_query_spec(
        specs,
        tables,
        "raw_section_chunks",
        "raw_chunk",
        f"SELECT section_index, chunk_index, byte_offset, byte_size, raw_sha256 "
        f"FROM {tables.get('raw_chunk', '')} WHERE {source} ORDER BY section_index, chunk_index "
        "LIMIT 1001",
        unit_metadata,
    )
    return specs


def _method_specs(method_table: str, source: str, die_offset: int) -> list[QuerySpec]:
    specs: list[QuerySpec] = []
    _add_query_spec(
        specs,
        {"index": method_table},
        "method_implementation_by_declaration",
        "index",
        f"SELECT unit_offset, die_offset FROM {method_table} WHERE {source} "
        "AND index_type = 'method_implementation' "
        f"AND target_offset = {die_offset} ORDER BY unit_offset, die_offset LIMIT 1001",
        {"declaration_offset": die_offset},
    )
    return specs


def run_query_with_metrics(
    name: str,
    operation: Callable[[], list[tuple[Any, ...]]],
    iterations: int,
    *,
    sql: str | None = None,
    diagnostics: DorisDiagnosticRecorder | None = None,
    **metadata: object,
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """Measure one Doris query and return its bounded result rows for chaining."""
    statement_id = None
    if diagnostics is not None and sql is not None:
        statement_id = diagnostics.prepare_statement(name, sql, metadata)
    result, cold_metrics = measure(operation)
    if diagnostics is not None and statement_id is not None:
        diagnostics.capture_execution(
            statement_id,
            state="cold",
            iteration=1,
            result_rows=result,
            result_hash=ordered_result_sha256(result),
            query_duration_seconds=float(cold_metrics["wall_seconds"]),
            measured_metrics=cold_metrics,
        )
    warm_samples: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        warm_result, warm_metrics = measure(operation)
        warm_samples.append(warm_metrics)
        if diagnostics is not None and statement_id is not None:
            diagnostics.capture_execution(
                statement_id,
                state="warm",
                iteration=iteration,
                result_rows=warm_result,
                result_hash=ordered_result_sha256(warm_result),
                query_duration_seconds=float(warm_metrics["wall_seconds"]),
                measured_metrics=warm_metrics,
            )
    measurement: dict[str, Any] = {
        "query": name,
        **metadata,
        "status": "complete" if result else "not_found",
        "matches": len(result),
        "limit": 1001,
        "ordered_result_sha256": _ordered_result_sha256(result),
        "cold": cold_metrics,
        "warm": distribution(warm_samples),
    }
    if statement_id is not None:
        measurement["diagnostic_statement_id"] = statement_id
    return (
        measurement,
        result,
    )


def _ordered_result_sha256(rows: list[tuple[Any, ...]]) -> str:
    """Hash result values in returned order without depending on repr formatting."""
    payload = [[_digest_value(value) for value in row] for row in rows]
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _digest_value(value: Any) -> dict[str, object]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    value_type = type(value)
    return {
        "type": f"{value_type.__module__}.{value_type.__qualname__}",
        "value": str(value),
    }


def doris_table_name(config: DorisConfig, family: str) -> str:
    table = f"{config.table}_{family}"
    return f"{quote_doris_identifier(config.database)}.{quote_doris_identifier(table)}"


def quote_doris_identifier(value: str) -> str:
    if not value or not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{value}`"


def sql_literal_for_benchmark(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def two_offsets(row: tuple[Any, ...]) -> tuple[int | None, int | None]:
    values = tuple(
        value if isinstance(value, int) and not isinstance(value, bool) else None
        for value in row[:2]
    )
    return values if len(values) == 2 else (None, None)


def _load_manifest_for_benchmark(path: Path) -> MaterializationManifest:
    return load_manifest(path)

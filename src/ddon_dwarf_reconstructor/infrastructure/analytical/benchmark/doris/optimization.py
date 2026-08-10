"""Opt-in Doris optimization matrix and source-bound lookup candidates."""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from ...doris import DorisConfig
from ...doris_layout import _identifier
from ...doris_optimization import DorisOptimizationReport
from ...manifest import load_manifest
from ...optional import import_optional
from .current import run_current_doris_benchmark
from .optimization_catalog import (
    DorisOptimizationCandidate,
)
from .optimization_catalog import (
    physical_candidates as _physical_candidates,
)
from .optimization_catalog import rejected_candidates as _rejected_candidates
from .optimization_environment import candidate_environment as _candidate_environment
from .optimization_preparation import prepare_candidate as _prepare_candidate


def build_optimization_matrix(config: DorisConfig) -> tuple[DorisOptimizationCandidate, ...]:
    """Return the deterministic one-factor-at-a-time evaluation matrix."""
    return tuple(
        [
            *_baseline_candidates(config),
            *_lookup_candidates(config),
            *_physical_candidates(),
            *_rejected_candidates(),
        ]
    )


def _baseline_candidates(config: DorisConfig) -> tuple[DorisOptimizationCandidate, ...]:
    return (
        _promoted_canonical_candidate(config),
        DorisOptimizationCandidate(
            "typed-projections",
            "query-shape",
            "not_observed",
            "Exact decoded-only generator projection; improves memory but misses the latency gate.",
            {
                "attribute_projection": "serving",
                "lossless_raw_values": False,
                "runtime_only": True,
            },
        ),
        DorisOptimizationCandidate(
            "batched-hydration",
            "query-shape",
            "not_observed",
            "Requires a trace-confirmed N+1 sequence.",
            {"batch_size": 512},
        ),
        DorisOptimizationCandidate(
            "reference-prefetch-lazy",
            "query-shape",
            "observed",
            "Exact trace-confirmed candidate; paired gain is below the 10% promotion gate.",
            {"reference_prefetch": "lazy", "runtime_only": True},
        ),
        DorisOptimizationCandidate(
            "combined-positive-below-gate",
            "interaction",
            "observed",
            "Historical confirmatory interaction; its serving policy is now the canonical default.",
            {
                "components": (
                    "reference-prefetch-lazy",
                    "typed-projections",
                    "name-lookup-b8",
                ),
                "reference_prefetch": "lazy",
                "attribute_projection": "serving",
                "lookup_table": f"{config.table}_opt_name_b8",
                "provision_lookup_candidates": (
                    "name-lookup-b2",
                    "name-lookup-b4",
                    "name-lookup-b8",
                ),
                "promoted_default": True,
            },
            f"{config.table}_opt_name_b8",
        ),
        DorisOptimizationCandidate(
            "unit-bound-hydration",
            "query-shape",
            "not_observed",
            "Source/unit-bound attribute, reference, and child-tag scans; requires exact confirmation.",
            {"hydration_scope": "unit", "runtime_only": True},
        ),
    )


def _promoted_canonical_candidate(config: DorisConfig) -> DorisOptimizationCandidate:
    return DorisOptimizationCandidate(
        "canonical",
        "baseline",
        "observed",
        "Promoted source-bound serving path: lazy prefetch, serving projection, and name lookup b8.",
        {
            "storage_format": "V2",
            "compression": "zstd",
            "statistics_policy": config.statistics_policy,
            "reference_prefetch": config.reference_prefetch,
            "attribute_projection": config.attribute_projection,
            "lookup_table": config.effective_name_lookup_table,
            "child_tag_filter": config.child_tag_filter,
            "hydration_scope": config.hydration_scope,
            "promoted_default": True,
        },
        config.table,
    )


def _lookup_candidates(config: DorisConfig) -> tuple[DorisOptimizationCandidate, ...]:
    names = tuple(_name_lookup_candidate(config, buckets) for buckets in (2, 4, 8))
    return (
        *names,
        DorisOptimizationCandidate(
            "method-target-b4",
            "lookup-table",
            "not_observed",
            "Run only when target-offset predicates meet the trace threshold.",
            {"buckets": 4, "distribution": "HASH(source_id,target_offset)"},
            f"{config.table}_opt_method_target_b4",
        ),
        DorisOptimizationCandidate(
            "die-offset-b4",
            "lookup-table",
            "not_observed",
            "Run only when global DIE-offset predicates meet the trace threshold.",
            {"buckets": 4, "distribution": "HASH(source_id,die_offset)"},
            f"{config.table}_opt_die_offset_b4",
        ),
    )


def _name_lookup_candidate(config: DorisConfig, buckets: int) -> DorisOptimizationCandidate:
    return DorisOptimizationCandidate(
        f"name-lookup-b{buckets}",
        "lookup-table",
        "not_observed",
        "Source/name lookup candidate; requires exact parity and full-generation benefit.",
        {"buckets": buckets, "distribution": "HASH(source_id,name)"},
        f"{config.table}_opt_name_b{buckets}",
    )


def lookup_candidate_sql(config: DorisConfig, candidate_id: str) -> tuple[str, ...]:
    """Build isolated DDL and source-bound population SQL for lookup candidates."""
    database = _identifier(config.database)
    if candidate_id.startswith("name-lookup-b"):
        buckets = _bucket_suffix(candidate_id)
        table = _identifier(f"{config.table}_opt_name_b{buckets}")
        return _index_lookup_sql(
            database,
            table,
            buckets,
            key="source_id, name, unit_offset, die_offset",
            distribution="source_id, name",
            predicate="index_type = 'definition'",
        )
    if candidate_id == "method-target-b4":
        table = _identifier(f"{config.table}_opt_method_target_b4")
        return _index_lookup_sql(
            database,
            table,
            4,
            key="source_id, target_offset, unit_offset, die_offset",
            distribution="source_id, target_offset",
            predicate="index_type = 'method_implementation'",
        )
    if candidate_id == "die-offset-b4":
        table = _identifier(f"{config.table}_opt_die_offset_b4")
        base = _identifier(f"{config.table}_die")
        return (
            f"CREATE TABLE IF NOT EXISTS {database}.{table} ("
            "source_id CHAR(64) NOT NULL, die_offset BIGINT NOT NULL, "
            "unit_offset BIGINT NOT NULL, ordinal BIGINT NOT NULL, tag VARCHAR(128), "
            "abbrev_code BIGINT, depth INT, parent_offset BIGINT, has_children BOOLEAN, "
            "is_null BOOLEAN"
            ") ENGINE=OLAP DUPLICATE KEY(source_id, die_offset, unit_offset, ordinal) "
            f"DISTRIBUTED BY HASH(source_id, die_offset) BUCKETS 4 "
            'PROPERTIES ("replication_num" = "1", "compression" = "zstd")',
            f"DELETE FROM {database}.{table} WHERE source_id = %s",
            f"INSERT INTO {database}.{table} (source_id, die_offset, unit_offset, ordinal, tag, "
            f"abbrev_code, depth, parent_offset, has_children, is_null) SELECT source_id, die_offset, "
            f"unit_offset, ordinal, tag, abbrev_code, depth, parent_offset, has_children, is_null FROM {database}.{base} "
            "WHERE source_id = %s",
        )
    raise ValueError(f"candidate does not have a lookup SQL contract: {candidate_id}")


def _index_lookup_sql(
    database: str,
    table: str,
    buckets: int,
    *,
    key: str,
    distribution: str,
    predicate: str,
) -> tuple[str, ...]:
    base = f"{table.removeprefix('`').removesuffix('`')}"
    source = f"{base.removesuffix('_opt_name_b' + str(buckets))}"
    if "method_target" in base:
        source = source.removesuffix("_opt_method_target_b4")
    source_table = f"{source}_index"
    return (
        f"CREATE TABLE IF NOT EXISTS {database}.{table} ("
        "source_id CHAR(64) NOT NULL, name VARCHAR(1024), unit_offset BIGINT NOT NULL, "
        "die_offset BIGINT NOT NULL, index_type VARCHAR(64) NOT NULL, tag VARCHAR(128), "
        "target_offset BIGINT, resolution_status VARCHAR(32)"
        f") ENGINE=OLAP DUPLICATE KEY({key}) DISTRIBUTED BY HASH({distribution}) "
        f'BUCKETS {buckets} PROPERTIES ("replication_num" = "1", "compression" = "zstd")',
        f"DELETE FROM {database}.{table} WHERE source_id = %s",
        f"INSERT INTO {database}.{table} (source_id, name, unit_offset, die_offset, index_type, "
        f"tag, target_offset, resolution_status) SELECT source_id, name, unit_offset, die_offset, "
        f"index_type, tag, target_offset, resolution_status FROM {database}.`{source_table}` "
        f"WHERE source_id = %s AND {predicate}",
    )


def _bucket_suffix(candidate_id: str) -> int:
    try:
        return int(candidate_id.rsplit("b", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"invalid lookup candidate bucket suffix: {candidate_id}") from error


def run_doris_optimization_benchmark(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    *,
    candidate_id: str = "canonical",
    provision_candidate: bool = False,
    control_symbols: tuple[str, ...] = ("MtObject", "rLayout"),
    control_cold_iterations: int = 3,
    control_warm_iterations: int = 5,
    query_iterations: int = 5,
    aifsm_cold_iterations: int = 1,
    aifsm_iterations: int = 3,
    control_timeout_seconds: float = 900.0,
    aifsm_timeout_seconds: float = 7200.0,
    sample_interval: float = 1.0,
    doris_cli: Path | None = None,
    trace_generation_queries: bool = False,
    trace_profile_threshold_ms: float = 500.0,
    trace_max_profiles: int = 20,
) -> dict[str, Any]:
    """Run the representative baseline or one explicitly provisioned candidate."""
    config = DorisConfig.from_environment()
    candidates = build_optimization_matrix(config)
    selected = _selected_candidate(candidates, candidate_id)
    output_dir = output_dir.resolve()
    run_output, provisioning, early_report = _prepare_candidate(
        elf,
        store_manifest,
        output_dir,
        config,
        candidates,
        selected,
        provision_candidate,
        _provision_candidate,
        _provision_combined_candidate,
    )
    if early_report is not None:
        _write_json(output_dir / "doris-optimization.json", early_report)
        return early_report
    baseline = _run_selected_candidate(
        elf,
        store_manifest,
        run_output,
        config,
        selected,
        control_symbols,
        control_cold_iterations,
        control_warm_iterations,
        query_iterations,
        aifsm_cold_iterations,
        aifsm_iterations,
        control_timeout_seconds,
        aifsm_timeout_seconds,
        sample_interval,
        doris_cli,
        trace_generation_queries,
        trace_profile_threshold_ms,
        trace_max_profiles,
    )
    report = _build_optimization_report(baseline, selected, candidates, provisioning)
    _write_json(output_dir / "doris-optimization.json", report)
    return report


def _selected_candidate(
    candidates: tuple[DorisOptimizationCandidate, ...], candidate_id: str
) -> DorisOptimizationCandidate:
    selected = next((item for item in candidates if item.candidate_id == candidate_id), None)
    if selected is None:
        raise ValueError(f"unknown Doris optimization candidate: {candidate_id}")
    return selected


def _run_selected_candidate(
    elf: Path,
    store_manifest: Path,
    run_output: Path,
    config: DorisConfig,
    selected: DorisOptimizationCandidate,
    control_symbols: tuple[str, ...],
    control_cold_iterations: int,
    control_warm_iterations: int,
    query_iterations: int,
    aifsm_cold_iterations: int,
    aifsm_iterations: int,
    control_timeout_seconds: float,
    aifsm_timeout_seconds: float,
    sample_interval: float,
    doris_cli: Path | None,
    trace_generation_queries: bool,
    trace_profile_threshold_ms: float,
    trace_max_profiles: int,
) -> dict[str, Any]:
    with _environment_overlay(_candidate_environment(config, selected)):
        return run_current_doris_benchmark(
            elf,
            store_manifest,
            run_output,
            control_symbols=control_symbols,
            control_iterations=control_warm_iterations,
            query_iterations=query_iterations,
            aifsm_iterations=aifsm_iterations,
            control_timeout_seconds=control_timeout_seconds,
            aifsm_timeout_seconds=aifsm_timeout_seconds,
            sample_interval=sample_interval,
            doris_cli=doris_cli,
            control_cold_iterations=control_cold_iterations,
            control_warm_iterations=control_warm_iterations,
            aifsm_cold_iterations=aifsm_cold_iterations,
            trace_generation_queries=trace_generation_queries,
            trace_profile_threshold_ms=trace_profile_threshold_ms,
            trace_max_profiles=trace_max_profiles,
        )


def _build_optimization_report(
    baseline: dict[str, Any],
    selected: DorisOptimizationCandidate,
    candidates: tuple[DorisOptimizationCandidate, ...],
    provisioning: dict[str, object],
) -> dict[str, Any]:
    report = dict(baseline)
    report["workload"] = "doris-optimization"
    promotion_gate = {
        "minimum_improvement_percent": 10,
        "maximum_regression_percent": 10,
        "parity_required": True,
    }
    matrix = _matrix_with_selected_status(candidates, selected.candidate_id, report["status"])
    report["optimization"] = {
        "selected_candidate": selected.to_dict(),
        "matrix": matrix,
        "provisioning": provisioning,
        "promotion_gate": promotion_gate,
    }
    report["optimization_report"] = DorisOptimizationReport.from_current_report(
        report,
        selected_candidate=selected.to_dict(),
        matrix=matrix,
        promotion_gate=promotion_gate,
    ).to_dict()
    return report


def _provision_candidate(
    elf: Path, store_manifest: Path, config: DorisConfig, candidate: DorisOptimizationCandidate
) -> dict[str, object]:
    del elf
    manifest = load_manifest(store_manifest.resolve())
    if manifest.status != "complete":
        raise ValueError("lookup candidate provisioning requires a complete manifest")
    if not candidate.table_name:
        raise ValueError(f"candidate has no table provisioning contract: {candidate.candidate_id}")
    if candidate.candidate_id not in {
        "method-target-b4",
        "die-offset-b4",
        "name-lookup-b2",
        "name-lookup-b4",
        "name-lookup-b8",
    }:
        raise ValueError(f"candidate provisioning is not implemented: {candidate.candidate_id}")
    pymysql = import_optional("pymysql", "analytical")
    connection = pymysql.connect(
        host=config.sql_host,
        port=config.sql_port,
        user=config.user,
        password=config.password,
        database=config.database,
        autocommit=True,
    )
    try:
        statements = lookup_candidate_sql(config, candidate.candidate_id)
        qualified_table = f"{_identifier(config.database)}.{_identifier(candidate.table_name)}"
        started = perf_counter()
        with connection.cursor() as cursor:
            cursor.execute(statements[0])
            cursor.execute(statements[1], (manifest.source_identity.sha256,))
            cursor.execute(statements[2], (manifest.source_identity.sha256,))
            cursor.execute(
                f"SELECT COUNT(*) FROM {qualified_table} WHERE source_id = %s",
                (manifest.source_identity.sha256,),
            )
            count_rows = cursor.fetchall()
            table_stats = _capture_candidate_rows(cursor, f"SHOW TABLE STATS {qualified_table}")
            tablet_stats = _capture_candidate_rows(cursor, f"SHOW TABLETS FROM {qualified_table}")
        row_count = int(count_rows[0][0]) if count_rows else 0
        return {
            "status": "observed",
            "candidate_id": candidate.candidate_id,
            "source_id": manifest.source_identity.sha256,
            "table": candidate.table_name,
            "row_count": row_count,
            "population_seconds": perf_counter() - started,
            "ddl_sha256": _sha256_text(statements[0]),
            "population_sql_sha256": _sha256_text(statements[2]),
            "table_stats": table_stats,
            "tablet_stats": tablet_stats,
        }
    finally:
        connection.close()


def _provision_combined_candidate(
    elf: Path,
    store_manifest: Path,
    config: DorisConfig,
) -> dict[str, object]:
    candidates = {
        candidate.candidate_id: candidate
        for candidate in _lookup_candidates(config)
        if candidate.candidate_id in {"name-lookup-b2", "name-lookup-b4", "name-lookup-b8"}
    }
    components = [
        _provision_candidate(elf, store_manifest, config, candidates[candidate_id])
        for candidate_id in ("name-lookup-b2", "name-lookup-b4", "name-lookup-b8")
    ]
    manifest = load_manifest(store_manifest.resolve())
    return {
        "status": "observed",
        "candidate_id": "combined-positive-below-gate",
        "source_id": manifest.source_identity.sha256,
        "active_lookup_candidate": "name-lookup-b8",
        "components": components,
    }


def _capture_candidate_rows(cursor: Any, statement: str) -> dict[str, object]:
    try:
        cursor.execute(statement)
        names = [str(column[0]) for column in (cursor.description or ())]
        rows = [
            dict(zip(names, row, strict=False)) if names else list(row) for row in cursor.fetchall()
        ]
        return {"status": "observed", "statement": statement, "rows": rows}
    except Exception as error:  # candidate evidence is additive to the query result
        return {"status": "partial", "statement": statement, "error": str(error), "rows": []}


def _matrix_with_selected_status(
    candidates: tuple[DorisOptimizationCandidate, ...], selected_id: str, status: object
) -> list[dict[str, object]]:
    return [
        {
            **candidate.to_dict(),
            "status": (
                str(status)
                if candidate.candidate_id == selected_id
                and candidate.status not in {"rejected", "not_applicable"}
                else candidate.status
            ),
        }
        for candidate in candidates
    ]


@contextmanager
def _environment_overlay(values: dict[str, str]) -> Generator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


__all__ = [
    "DorisOptimizationCandidate",
    "build_optimization_matrix",
    "lookup_candidate_sql",
    "run_doris_optimization_benchmark",
]

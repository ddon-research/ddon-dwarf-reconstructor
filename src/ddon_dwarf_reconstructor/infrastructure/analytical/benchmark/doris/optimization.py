"""Opt-in Doris optimization matrix and source-bound lookup candidates."""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from ...doris import DorisConfig
from ...doris_layout import _identifier
from ...doris_optimization import DorisOptimizationReport
from ...manifest import load_manifest
from ...optional import import_optional
from .current import run_current_doris_benchmark
from .optimization_reports import not_observed_report as _not_observed_report


@dataclass(frozen=True, slots=True)
class DorisOptimizationCandidate:
    """One isolated, evidence-gated optimization variant."""

    candidate_id: str
    category: str
    status: str
    reason: str
    settings: dict[str, object]
    table_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "category": self.category,
            "status": self.status,
            "reason": self.reason,
            "settings": dict(self.settings),
            "table_name": self.table_name,
        }


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
        DorisOptimizationCandidate(
            "canonical",
            "baseline",
            "observed",
            "Existing source-bound serving projection.",
            {
                "storage_format": "V2",
                "compression": "zstd",
                "statistics_policy": config.statistics_policy,
            },
            config.table,
        ),
        DorisOptimizationCandidate(
            "typed-projections",
            "query-shape",
            "not_observed",
            "Requires an actual generation trace comparison.",
            {"select_star": False},
        ),
        DorisOptimizationCandidate(
            "batched-hydration",
            "query-shape",
            "not_observed",
            "Requires a trace-confirmed N+1 sequence.",
            {"batch_size": 512},
        ),
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


def _physical_candidates() -> tuple[DorisOptimizationCandidate, ...]:
    definitions = (
        ("drop-inverted-index", {"index_change": "remove_one_inverted_index"}),
        ("trim-redundant-bloom", {"index_change": "remove_key_column_bloom"}),
        ("bucket-tiny-one", {"bucket_change": "tiny_families_to_one_bucket"}),
        ("storage-v3-widest", {"storage_format": "V3", "family": "attribute"}),
        ("compression-lz4-widest", {"compression": "lz4", "family": "attribute"}),
        ("pipeline-parallelism", {"parallel_pipeline_task_num": "default,1,higher"}),
        ("sql-cache", {"enable_sql_cache": "off,on"}),
        ("stream-load-workers", {"workers": "1,2,4,8"}),
    )
    return tuple(
        DorisOptimizationCandidate(
            candidate_id,
            "physical-or-runtime",
            "not_observed",
            "Run as an isolated one-factor comparison.",
            dict(settings),
        )
        for candidate_id, settings in definitions
    )


def _rejected_candidates() -> tuple[DorisOptimizationCandidate, ...]:
    return (
        DorisOptimizationCandidate(
            "row-store",
            "rejected",
            "not_applicable",
            "The workload is append-only analytical Duplicate Key data, not Unique MOW point SELECT *.",
            {"store_row_column": False},
        ),
        DorisOptimizationCandidate(
            "async-materialized-view",
            "rejected",
            "not_applicable",
            "Exact immutable manifest binding is better served by an auxiliary table.",
            {"refresh": "not_promoted"},
        ),
        DorisOptimizationCandidate(
            "group-commit",
            "rejected",
            "not_applicable",
            "The publication is immutable bulk Stream Load rather than frequent small batches.",
            {"group_commit": False},
        ),
        DorisOptimizationCandidate(
            "complex-sql-features",
            "rejected",
            "not_applicable",
            "Current generation trace is single-table parameterized lookup work.",
            {"features": "cte,subquery,lateral,complex,multidimensional,runtime-filter"},
        ),
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


def _prepare_candidate(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    config: DorisConfig,
    candidates: tuple[DorisOptimizationCandidate, ...],
    selected: DorisOptimizationCandidate,
    provision_candidate: bool,
) -> tuple[Path, dict[str, object], dict[str, Any] | None]:
    run_output = output_dir / selected.candidate_id
    run_output.mkdir(parents=True, exist_ok=True)
    provisioning: dict[str, object] = {
        "status": "not_observed",
        "reason": "canonical serving projection was reused",
    }
    if selected.candidate_id == "canonical":
        return run_output, provisioning, None
    if not provision_candidate:
        return (
            run_output,
            provisioning,
            _not_observed_report(
                selected,
                candidates,
                config,
                output_dir,
                "--provision-candidate was not set",
            ),
        )
    try:
        provisioning = _provision_candidate(elf, store_manifest, config, selected)
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        report = _not_observed_report(
            selected,
            candidates,
            config,
            output_dir,
            f"candidate provisioning was blocked: {error}",
            status="blocked",
        )
        report["provisioning"] = {"status": "blocked", "reason": str(error)}
        return run_output, provisioning, report
    return run_output, provisioning, None


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
        with connection.cursor() as cursor:
            cursor.execute(statements[0])
            cursor.execute(statements[1], (manifest.source_identity.sha256,))
            cursor.execute(statements[2], (manifest.source_identity.sha256,))
            cursor.execute(
                f"SELECT COUNT(*) FROM {qualified_table} WHERE source_id = %s",
                (manifest.source_identity.sha256,),
            )
            rows = cursor.fetchall()
        row_count = int(rows[0][0]) if rows else 0
        return {
            "status": "observed",
            "candidate_id": candidate.candidate_id,
            "source_id": manifest.source_identity.sha256,
            "row_count": row_count,
            "ddl_sha256": _sha256_text(statements[0]),
            "population_sql_sha256": _sha256_text(statements[2]),
        }
    finally:
        connection.close()


def _matrix_with_selected_status(
    candidates: tuple[DorisOptimizationCandidate, ...], selected_id: str, status: object
) -> list[dict[str, object]]:
    return [
        {
            **candidate.to_dict(),
            "status": str(status) if candidate.candidate_id == selected_id else candidate.status,
        }
        for candidate in candidates
    ]


def _candidate_environment(
    config: DorisConfig, candidate: DorisOptimizationCandidate
) -> dict[str, str]:
    environment = {
        "DDON_DORIS_SERVING_VARIANT_ID": candidate.candidate_id,
    }
    if candidate.category != "lookup-table":
        return environment
    if candidate.candidate_id.startswith("name-lookup-"):
        table = candidate.table_name or ""
        environment["DDON_DORIS_NAME_LOOKUP_TABLE"] = table
        environment["DDON_DORIS_DEFINITION_LOOKUP_TABLE"] = table
    elif candidate.candidate_id == "method-target-b4":
        environment["DDON_DORIS_METHOD_LOOKUP_TABLE"] = candidate.table_name or ""
    elif candidate.candidate_id == "die-offset-b4":
        environment["DDON_DORIS_DIE_LOOKUP_TABLE"] = candidate.table_name or ""
    environment["DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE"] = "1"
    environment["DDON_DORIS_STATISTICS_POLICY"] = config.statistics_policy
    return environment


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

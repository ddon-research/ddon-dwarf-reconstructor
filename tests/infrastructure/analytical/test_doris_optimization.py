"""Tests for typed Doris optimization identities and generation traces."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.optimization as benchmark_optimization_module
import ddon_dwarf_reconstructor.infrastructure.analytical.doris_optimization as optimization_module
import ddon_dwarf_reconstructor.infrastructure.analytical.doris_validation as validation_module
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.optimization import (
    build_optimization_matrix,
    lookup_candidate_sql,
    run_doris_optimization_benchmark,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_diagnostics_transport import (
    DiagnosticTransportResult,
    DorisDiagnosticTransport,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_optimization import (
    DorisOptimizationReport,
    DorisQueryTraceConfig,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_optimization_utils import (
    configured_ddl_sha256,
    int_mapping,
    mapping_sequence,
    profile_metrics,
    query_shape,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_queries import DorisQueryExecutor
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_serving_profile import (
    DorisServingProfile,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_statistics import analyze_tables
from tests.support.doris_statistics import StatisticsConnection

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Cursor:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection
        self.description = (("name",),)
        self.rows: list[tuple[object, ...]] = [("value",)]

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback

    def execute(self, statement: str, params: object = ()) -> None:
        del params
        self.connection.statements.append(statement)
        if "last_query_id" in statement.lower():
            self.rows = [(f"query-{self.connection.query_count}",)]
            self.description = (("query_id",),)
        else:
            self.connection.query_count += 1

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class _Connection:
    def __init__(self) -> None:
        self.query_count = 0
        self.statements: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self)


def test_query_trace_records_actual_query_without_parameter_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def profile(_self: object, query_id: str, *, full: bool) -> DiagnosticTransportResult:
        assert full is True
        return DiagnosticTransportResult(
            "observed",
            "fake-fe",
            f"Query ID: {query_id}",
            {"query_id": query_id, "profile": {"summary": {"scan_bytes": 12}}},
        )

    monkeypatch.setattr(DorisDiagnosticTransport, "profile", profile)
    trace_path = tmp_path / "generation" / "queries.jsonl"
    config = DorisConfig(query_trace=DorisQueryTraceConfig(trace_path, max_profile_instances=1))
    connection = _Connection()
    executor = DorisQueryExecutor(connection, config, "a" * 64)

    rows = executor.family_rows(
        "index",
        {"name": "secret symbol"},
        columns=("name",),
    )
    executor.family_rows("index", {"name": "secret symbol"}, columns=("name",))
    executor.close()

    assert rows == ({"name": "value"},)
    record = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["family"] == "index"
    assert record["operation"] == "family_rows"
    assert record["profile_status"] == "observed"
    assert record["scan_bytes"] == 12
    assert record["scan_rows"] is None
    assert "secret symbol" not in trace_path.read_text(encoding="utf-8")
    assert Path(record["profile_artifact"]["path"]).is_file()
    summary = json.loads(trace_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert summary["counts"] == {
        "observed_count": 2,
        "partial_count": 0,
        "profile_count": 1,
        "query_count": 2,
        "shape_count": 1,
    }


def test_query_trace_marks_profile_id_mismatch_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def profile(_self: object, _query_id: str, *, full: bool) -> DiagnosticTransportResult:
        assert full is True
        return DiagnosticTransportResult(
            "observed",
            "fake-fe",
            "Query ID: stale-query",
            {"query_id": "stale-query", "profile": {}},
        )

    monkeypatch.setattr(DorisDiagnosticTransport, "profile", profile)
    trace_path = tmp_path / "mismatch" / "queries.jsonl"
    config = DorisConfig(query_trace=DorisQueryTraceConfig(trace_path))
    executor = DorisQueryExecutor(_Connection(), config, "b" * 64)
    executor.family_rows("index", {"name": "symbol"}, columns=("name",))
    executor.close()

    record = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "partial"
    assert record["profile_status"] == "partial"
    assert "requested query ID" in record["error"]


def test_query_trace_marks_missing_query_id_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(optimization_module, "_last_query_id", lambda _connection: (None, None))
    trace_path = tmp_path / "missing" / "queries.jsonl"
    config = DorisConfig(query_trace=DorisQueryTraceConfig(trace_path))
    executor = DorisQueryExecutor(_Connection(), config, "c" * 64)
    executor.family_rows("index", {"name": "symbol"}, columns=("name",))
    executor.close()

    record = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "partial"
    assert record["profile_status"] == "partial"


def test_query_trace_marks_evicted_or_unavailable_profile_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_self: object, _query_id: str, *, full: bool) -> DiagnosticTransportResult:
        assert full is True
        return DiagnosticTransportResult("unavailable", "fake-fe", error="profile evicted")

    monkeypatch.setattr(DorisDiagnosticTransport, "profile", unavailable)
    trace_path = tmp_path / "evicted" / "queries.jsonl"
    config = DorisConfig(query_trace=DorisQueryTraceConfig(trace_path))
    executor = DorisQueryExecutor(_Connection(), config, "d" * 64)
    executor.family_rows("index", {"name": "symbol"}, columns=("name",))
    executor.close()

    record = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "partial"
    assert record["profile_status"] == "unavailable"


def test_serving_variant_fingerprint_includes_lookup_tables() -> None:
    canonical = DorisServingProfile.from_config(DorisConfig())
    candidate = DorisServingProfile.from_config(
        DorisConfig(name_lookup_table="dwarf_records_opt_name_b4"),
        variant_id="name-lookup-b4",
    )

    assert canonical.variant_id == "canonical"
    assert candidate.variant_id == "name-lookup-b4"
    assert candidate.configuration_sha256 != canonical.configuration_sha256


def test_serving_variant_fingerprint_includes_reference_prefetch_policy() -> None:
    eager = DorisServingProfile.from_config(
        DorisConfig(reference_prefetch="eager"), variant_id="reference-prefetch-eager"
    )
    lazy = DorisServingProfile.from_config(DorisConfig(reference_prefetch="lazy"))

    assert eager.configuration_sha256 != lazy.configuration_sha256
    assert lazy.to_dict()["reference_prefetch"] == "lazy"


def test_serving_variant_fingerprint_includes_attribute_projection() -> None:
    full = DorisServingProfile.from_config(
        DorisConfig(attribute_projection="full"), variant_id="attribute-projection-full"
    )
    serving = DorisServingProfile.from_config(DorisConfig(attribute_projection="serving"))

    assert full.configuration_sha256 != serving.configuration_sha256
    assert serving.to_dict()["attribute_projection"] == "serving"


def test_serving_variant_fingerprint_includes_child_tag_filter() -> None:
    full = DorisServingProfile.from_config(
        DorisConfig(child_tag_filter="all"), variant_id="child-tag-all"
    )
    targeted = DorisServingProfile.from_config(
        DorisConfig(child_tag_filter="targeted"), variant_id="child-tag-targeted"
    )

    assert full.configuration_sha256 != targeted.configuration_sha256
    assert targeted.to_dict()["child_tag_filter"] == "targeted"


def test_serving_variant_fingerprint_includes_hydration_scope() -> None:
    global_scope = DorisServingProfile.from_config(
        DorisConfig(hydration_scope="global"), variant_id="hydration-global"
    )
    unit_scope = DorisServingProfile.from_config(
        DorisConfig(hydration_scope="unit"), variant_id="hydration-unit"
    )

    assert global_scope.configuration_sha256 != unit_scope.configuration_sha256
    assert unit_scope.to_dict()["hydration_scope"] == "unit"


def test_serving_policy_configuration_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_REFERENCE_PREFETCH", "eager")
    monkeypatch.setenv("DDON_DORIS_ATTRIBUTE_PROJECTION", "full")
    monkeypatch.setenv("DDON_DORIS_NAME_LOOKUP_TABLE", "legacy_lookup")
    monkeypatch.setenv("DDON_DORIS_DEFINITION_LOOKUP_TABLE", "legacy_lookup")
    monkeypatch.setenv("DDON_DORIS_CHILD_TAG_FILTER", "targeted")
    monkeypatch.setenv("DDON_DORIS_HYDRATION_SCOPE", "unit")

    with pytest.raises(ValueError, match="canonical Doris serving policy"):
        DorisConfig.from_environment()


def test_noncanonical_variant_can_override_promoted_runtime_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_SERVING_VARIANT_ID", "name-lookup-b4")
    monkeypatch.setenv("DDON_DORIS_NAME_LOOKUP_TABLE", "dwarf_records_opt_name_b4")
    monkeypatch.setenv("DDON_DORIS_DEFINITION_LOOKUP_TABLE", "dwarf_records_opt_name_b4")
    monkeypatch.setenv("DDON_DORIS_REFERENCE_PREFETCH", "eager")
    monkeypatch.setenv("DDON_DORIS_ATTRIBUTE_PROJECTION", "full")

    config = DorisConfig.from_environment()

    assert config.serving_variant_id == "name-lookup-b4"
    assert config.effective_name_lookup_table == "dwarf_records_opt_name_b4"
    assert config.reference_prefetch == "eager"
    assert config.attribute_projection == "full"


def test_canonical_environment_rejects_statistics_and_lookup_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_STATISTICS_POLICY", "all")
    with pytest.raises(ValueError, match="canonical Doris serving policy"):
        DorisConfig.from_environment()

    monkeypatch.delenv("DDON_DORIS_STATISTICS_POLICY")
    monkeypatch.setenv("DDON_DORIS_METHOD_LOOKUP_TABLE", "optimized_methods")
    with pytest.raises(ValueError, match="canonical Doris serving policy"):
        DorisConfig.from_environment()


def test_canonical_lookup_override_uses_the_effective_base_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_TABLE", "alternate_records")
    monkeypatch.setenv("DDON_DORIS_NAME_LOOKUP_TABLE", "alternate_records_opt_name_b8")

    config = DorisConfig.from_environment()

    assert config.table == "alternate_records"
    assert config.effective_name_lookup_table == "alternate_records_opt_name_b8"


def test_sql_connection_timeouts_are_typed_environment_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDON_DORIS_SQL_CONNECT_TIMEOUT_SECONDS", "4.5")
    monkeypatch.setenv("DDON_DORIS_SQL_READ_TIMEOUT_SECONDS", "37")
    monkeypatch.setenv("DDON_DORIS_SQL_WRITE_TIMEOUT_SECONDS", "41")

    config = DorisConfig.from_environment()

    assert config.sql_connect_timeout_seconds == 4.5
    assert config.sql_read_timeout_seconds == 37.0
    assert config.sql_write_timeout_seconds == 41.0


@pytest.mark.parametrize(
    "field_name",
    ("sql_connect_timeout_seconds", "sql_read_timeout_seconds", "sql_write_timeout_seconds"),
)
def test_sql_connection_timeouts_must_be_positive(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        DorisConfig(**{field_name: 0.0})


def test_canonical_profile_rejects_direct_policy_overrides() -> None:
    with pytest.raises(ValueError, match="canonical Doris serving profile"):
        DorisServingProfile.from_config(DorisConfig(reference_prefetch="eager"))

    with pytest.raises(ValueError, match="canonical Doris serving profile"):
        DorisServingProfile.from_config(DorisConfig(name_lookup_table="dwarf_records_noncanonical"))


def test_optimization_matrix_keeps_canonical_and_rejects_inapplicable_paths() -> None:
    candidates = {item.candidate_id: item for item in build_optimization_matrix(DorisConfig())}
    assert candidates["canonical"].status == "observed"
    assert candidates["canonical"].settings["promoted_default"] is True
    assert candidates["canonical"].settings["lookup_table"] == "dwarf_records_opt_name_b8"
    assert candidates["reference-prefetch-lazy"].settings["reference_prefetch"] == "lazy"
    assert candidates["combined-positive-below-gate"].status == "observed"
    assert candidates["combined-positive-below-gate"].settings["promoted_default"] is True
    assert candidates["combined-positive-below-gate"].settings["components"] == (
        "reference-prefetch-lazy",
        "typed-projections",
        "name-lookup-b8",
    )
    assert candidates["typed-projections"].settings["attribute_projection"] == "serving"
    assert candidates["typed-projections"].settings["lossless_raw_values"] is False
    assert candidates["targeted-child-tag-filter"].status == "rejected"
    assert candidates["targeted-child-tag-filter"].settings["child_tag_filter"] == "targeted"
    assert candidates["unit-bound-hydration"].settings["hydration_scope"] == "unit"
    assert candidates["name-lookup-b4"].settings["distribution"] == "HASH(source_id,name)"
    assert candidates["grouped-child-tag-counts"].status == "rejected"
    assert candidates["row-store"].status == "not_applicable"
    assert candidates["async-materialized-view"].status == "not_applicable"


def test_lookup_candidate_sql_is_source_bound_and_isolated() -> None:
    statements = lookup_candidate_sql(DorisConfig(), "name-lookup-b4")

    assert "dwarf_records_opt_name_b4" in statements[0]
    assert "HASH(source_id, name)" in statements[0]
    assert "WHERE source_id = %s" in statements[2]
    assert "dwarf_records_index" in statements[2]
    assert "DROP TABLE" not in " ".join(statements)


def test_query_trace_config_rejects_unbounded_profile_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_profile_instances"):
        DorisQueryTraceConfig(tmp_path / "trace.jsonl", max_profile_instances=0)


def test_selective_statistics_policy_targets_filter_columns() -> None:
    connection = StatisticsConnection()
    config = DorisConfig(statistics_policy="selective")
    plan = SimpleNamespace(
        database="dwarf",
        table="dwarf_records",
        name_lookup_table=None,
        serving_variant_id="canonical",
    )

    statements = analyze_tables(connection, plan, config)

    assert len(statements) == 15
    assert "WITH SAMPLE ROWS 4194304" in connection.statements[0]
    assert "`source_id`" in connection.statements[0]
    assert "`details_json`" not in connection.statements[0]
    assert statements[-1]["table"] == "dwarf_records_opt_name_b8"
    assert "`name`" in statements[-1]["statement"]


def test_optimization_report_serializes_cold_warm_traces_and_rejections() -> None:
    current = {
        "status": "observed",
        "source_identity": {"sha256": "a" * 64},
        "store_manifest": "manifest.json",
        "serving_variant": {"variant_id": "canonical"},
        "serving_validation": {"observed_counts": {"die": 3}},
        "backend": {"type": "native_doris"},
        "runs": [
            {
                "symbol": "rLayout",
                "state": "cold",
                "iteration": 1,
                "query_trace": {"status": "observed", "counts": {"query_count": 2}},
                "output": {"files": [{"path": "rLayout.h", "sha256": "b" * 64}]},
            },
            {
                "symbol": "rLayout",
                "state": "long",
                "iteration": 1,
                "query_trace": {"status": "not_observed"},
                "output": {"files": []},
            },
        ],
    }
    matrix = [
        {"candidate_id": "canonical", "category": "baseline", "status": "observed"},
        {"candidate_id": "row-store", "category": "rejected", "status": "not_applicable"},
    ]

    report = DorisOptimizationReport.from_current_report(
        current,
        selected_candidate=matrix[0],
        matrix=matrix,
        promotion_gate={"minimum_improvement_percent": 10},
    ).to_dict()

    assert report["complete_row_counts"] == {"die": 3}
    assert len(report["cold_samples"]) == 1
    assert len(report["warm_samples"]) == 1
    assert len(report["query_traces"]) == 1
    assert report["rejected_optimizations"][0]["candidate_id"] == "row-store"
    assert json.loads(json.dumps(report, sort_keys=True))["schema_version"] == "1.0"


def test_query_trace_helpers_normalize_shapes_and_profile_metrics() -> None:
    assert query_shape("SELECT 12  FROM t WHERE id = 42") == "SELECT ? FROM t WHERE id = ?"
    assert profile_metrics({"fragment": {"scan_bytes": 12, "memory": 8}})["scan_bytes"] == 12
    assert mapping_sequence("not-a-sequence") == ()
    assert int_mapping({"zero": 0, "negative": "-2", "ignored": "x"}) == {
        "zero": 0,
        "negative": -2,
    }
    ddl_hash = configured_ddl_sha256(DorisConfig(database="dwarf", table="records"))
    assert len(ddl_hash) == 64


def test_doris_load_plan_validation_is_source_bound_and_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = SimpleNamespace(status="complete", configuration={})
    path = tmp_path / "manifest.json"
    plan_path = tmp_path / "part-index.parquet"
    plan = SimpleNamespace(
        parquet_files=(plan_path,),
        database="dwarf",
        table="records",
        statistics_policy="selective",
        serving_variant_id="canonical",
        stream_load_workers=1,
    )
    config = SimpleNamespace(
        database="dwarf",
        table="records",
        statistics_policy="selective",
        serving_variant_id="canonical",
        stream_load_workers=1,
    )
    monkeypatch.setattr(validation_module, "has_parser_diagnostics", lambda _manifest: False)
    monkeypatch.setattr(validation_module, "has_unapplied_source_recovery", lambda _manifest: False)
    monkeypatch.setattr(
        validation_module, "declared_parquet_files", lambda _path, _manifest: (plan_path,)
    )
    validation_module.validate_manifest_for_load(manifest, path)
    validation_module.validate_plan_files(plan, path, manifest)
    validation_module.validate_plan_settings(plan, config)

    observed: list[tuple[Path, object, bool, bool]] = []
    monkeypatch.setattr(
        validation_module,
        "validate_manifest_files",
        lambda *args, **kwargs: observed.append(
            (args[0], args[1], kwargs["verify_hashes"], kwargs["verify_payload"])
        ),
    )
    validation_module.validate_plan_manifest_files(path, manifest)
    assert observed == [(path, manifest, True, True)]
    with pytest.raises(ValueError, match="connection table"):
        validation_module.validate_plan_settings(
            plan, config.__class__(**{**vars(config), "table": "other"})
        )
    with pytest.raises(ValueError, match="Parquet"):
        validation_module.validate_plan_files(
            SimpleNamespace(**{**vars(plan), "parquet_files": ()}), path, manifest
        )


def test_doris_optimization_noncanonical_candidate_is_explicitly_unobserved(tmp_path: Path) -> None:
    report = run_doris_optimization_benchmark(
        Path("source.elf"),
        Path("manifest.json"),
        tmp_path,
        candidate_id="name-lookup-b4",
        provision_candidate=False,
    )

    assert report["status"] == "not_observed"
    assert report["optimization"]["selected_candidate"]["candidate_id"] == "name-lookup-b4"
    assert report["optimization_report"]["status"] == "not_observed"


def test_lookup_candidate_routes_and_environment_are_isolated() -> None:
    method = benchmark_optimization_module.lookup_candidate_sql(DorisConfig(), "method-target-b4")
    die = benchmark_optimization_module.lookup_candidate_sql(DorisConfig(), "die-offset-b4")
    assert "target_offset" in method[0] and "method_implementation" in method[2]
    assert "dwarf_records_die" in die[2]
    candidates = {item.candidate_id: item for item in build_optimization_matrix(DorisConfig())}
    assert benchmark_optimization_module._candidate_environment(
        DorisConfig(), candidates["name-lookup-b4"]
    )["DDON_DORIS_NAME_LOOKUP_TABLE"].endswith("_b4")
    assert benchmark_optimization_module._candidate_environment(
        DorisConfig(), candidates["method-target-b4"]
    )["DDON_DORIS_METHOD_LOOKUP_TABLE"].endswith("_b4")
    assert (
        benchmark_optimization_module._candidate_environment(
            DorisConfig(), candidates["reference-prefetch-lazy"]
        )["DDON_DORIS_REFERENCE_PREFETCH"]
        == "lazy"
    )
    assert (
        benchmark_optimization_module._candidate_environment(
            DorisConfig(), candidates["typed-projections"]
        )["DDON_DORIS_ATTRIBUTE_PROJECTION"]
        == "serving"
    )
    assert (
        benchmark_optimization_module._candidate_environment(
            DorisConfig(), candidates["targeted-child-tag-filter"]
        )["DDON_DORIS_CHILD_TAG_FILTER"]
        == "targeted"
    )
    assert (
        benchmark_optimization_module._candidate_environment(
            DorisConfig(), candidates["unit-bound-hydration"]
        )["DDON_DORIS_HYDRATION_SCOPE"]
        == "unit"
    )
    batch = benchmark_optimization_module._candidate_environment(
        DorisConfig(), candidates["combined-positive-below-gate"]
    )
    assert batch["DDON_DORIS_REFERENCE_PREFETCH"] == "lazy"
    assert batch["DDON_DORIS_ATTRIBUTE_PROJECTION"] == "serving"
    assert batch["DDON_DORIS_NAME_LOOKUP_TABLE"].endswith("_opt_name_b8")


def test_runtime_only_candidate_does_not_require_table_provisioning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        benchmark_optimization_module,
        "run_current_doris_benchmark",
        lambda *args, **kwargs: {
            "status": "observed",
            "runs": [],
            "serving_validation": {},
        },
    )
    report = run_doris_optimization_benchmark(
        Path("source.elf"),
        Path("manifest.json"),
        tmp_path,
        candidate_id="reference-prefetch-lazy",
        provision_candidate=False,
        control_cold_iterations=1,
        control_warm_iterations=1,
        query_iterations=1,
        aifsm_iterations=1,
    )

    assert report["status"] == "observed"
    assert report["optimization"]["provisioning"]["status"] == "not_applicable"


def test_candidate_evidence_capture_serializes_rows_and_failures() -> None:
    observed = benchmark_optimization_module._capture_candidate_rows(
        _Cursor(_Connection()), "SHOW TABLE STATS dwarf.records"
    )
    assert observed["status"] == "observed"
    assert observed["rows"] == [{"name": "value"}]

    class FailingCursor:
        description: tuple[tuple[str], ...] = ()

        def execute(self, _statement: str) -> None:
            raise RuntimeError("candidate stats unavailable")

        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    partial = benchmark_optimization_module._capture_candidate_rows(
        FailingCursor(), "SHOW TABLETS FROM dwarf.records"
    )
    assert partial["status"] == "partial"
    assert "unavailable" in str(partial["error"])

"""Bounded benchmark protocol for the analytical store and native Doris."""

from __future__ import annotations

import json
import os
import platform
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from .....domain.models.analytical_dwarf import DwarfMaterializationRequest
from ...artifact_store import load_analytical_store
from ...doris import DorisConfig, DorisLoader, build_doris_plan
from ...manifest import declared_parquet_files, load_manifest
from ...materializer import DwarfMaterializer
from ...optional import AnalyticalDependencyError
from ..doris.queries import doris_queries
from .baselines import current_runtime_baseline
from .metrics import measure
from .output import safe_output_name, tree_digest


def run_store_benchmark(
    elf: Path,
    output_dir: Path,
    *,
    store_manifest: Path | None = None,
    symbols: tuple[str, ...] = ("MtObject", "rLayout"),
    run_doris: bool = False,
    iterations: int = 3,
    run_current_baseline: bool = False,
    allow_incomplete: bool = False,
    run_knowledge_export: bool = False,
    query_existing_doris: bool = False,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if run_doris and query_existing_doris:
        raise ValueError("run_doris and query_existing_doris are mutually exclusive")
    output_dir.mkdir(parents=True, exist_ok=True)
    baselines = _baseline_measurements(
        elf,
        output_dir,
        symbols,
        iterations,
        run_current_baseline=run_current_baseline,
    )
    store_manifest, measurements = _prepare_store(
        elf,
        output_dir,
        store_manifest,
    )
    store, load_metrics = measure(
        lambda: load_analytical_store(
            store_manifest,
            source_path=elf,
            allow_incomplete=allow_incomplete,
        )
    )
    measurements["load_store"] = {
        "status": "partial" if store.manifest.status != "complete" else "observed",
        **load_metrics,
        "units": store.unit_count,
        "dies": store.die_count,
    }
    measurements.update(
        _runtime_measurements(
            store_manifest,
            store,
            run_doris,
            query_existing_doris,
            symbols,
            iterations,
            allow_incomplete=allow_incomplete,
            run_knowledge_export=run_knowledge_export,
        )
    )
    measurements["artifacts"] = _artifact_measurement(store_manifest)
    report = _build_report(store, measurements, baselines)
    _write_report(output_dir / "benchmark-report.json", report)
    return report


def _prepare_store(
    elf: Path,
    output_dir: Path,
    store_manifest: Path | None,
) -> tuple[Path, dict[str, Any]]:
    measurements: dict[str, Any] = {}
    if store_manifest is not None:
        measurements["materialize_store"] = {
            "status": "not_observed",
            "reason": "A pre-existing source-bound manifest was supplied.",
        }
        return store_manifest.resolve(), measurements

    materializer = DwarfMaterializer()
    manifest, metrics = measure(
        lambda: materializer.materialize(
            DwarfMaterializationRequest(
                source_path=elf,
                output_dir=output_dir,
                write_jsonl=False,
                write_parquet=True,
            )
        )
    )
    manifest_path = materializer.last_manifest_path
    if manifest_path is None:
        raise RuntimeError("Materializer did not publish a manifest path")
    measurements["materialize_parquet"] = {
        "status": "observed",
        **metrics,
        "cu_passes": materializer.cu_passes,
        "counts": manifest.counts,
    }
    return manifest_path.resolve(), measurements


def _runtime_measurements(
    store_manifest: Path,
    store: Any,
    run_doris: bool,
    query_existing_doris: bool,
    symbols: tuple[str, ...],
    iterations: int,
    *,
    allow_incomplete: bool,
    run_knowledge_export: bool,
) -> dict[str, Any]:
    partial = allow_incomplete and store.manifest.status != "complete"
    return {
        "doris": (
            {
                "status": "not_observed",
                "reason": "Doris loading requires a complete analytical store.",
            }
            if partial
            else _doris_measurement(
                store_manifest,
                run_doris,
                query_existing_doris,
                symbols,
                iterations,
            )
        ),
        "knowledge_export": (
            {
                "status": "not_observed",
                "reason": "Knowledge export requires a complete analytical store.",
            }
            if partial
            else (
                _knowledge_export_measurement(store_manifest, store, symbols, iterations)
                if run_knowledge_export
                else {
                    "status": "not_observed",
                    "reason": "Pass --run-knowledge-export for complete export evidence.",
                }
            )
        ),
    }


def _knowledge_export_measurement(
    store_manifest: Path,
    store: Any,
    symbols: tuple[str, ...],
    iterations: int,
    *,
    session_factory: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    del iterations
    try:
        from .....application.generators import DwarfGenerator
        from .....infrastructure.artifacts import SourceIdentityCatalog
        from .....infrastructure.composition import create_disassembly_producer, create_dump_lookup
        from .....infrastructure.config import DwarfRuntimeConfig
        from ...session import AnalyticalDwarfSession

        output_root = store_manifest.resolve().parent / "knowledge-export"
        output_root.mkdir(parents=True, exist_ok=True)
        runtime = DwarfRuntimeConfig.from_environment()
        identity_catalog = SourceIdentityCatalog()
        source_path = Path(store.manifest.source_path)
        store_path = store_manifest.resolve()

        def operation() -> tuple[list[Path], int]:
            exported: list[Path] = []

            def default_session_factory(_path: Path) -> AnalyticalDwarfSession:
                return AnalyticalDwarfSession(store_path, expected_source_path=source_path)

            with DwarfGenerator(
                source_path,
                session_factory=session_factory or default_session_factory,
                dump_lookup_factory=create_dump_lookup,
                disassembly_factory=create_disassembly_producer,
                cache_file=output_root / "dwarf-cache.json",
                die_cache_size=runtime.die_cache_size,
                type_cache_size=runtime.type_cache_size,
                search_timeout=runtime.search_timeout_seconds,
                source_hash=identity_catalog.sha256,
                source_identity=identity_catalog,
            ) as generator:
                for symbol in symbols:
                    symbol_root = output_root / safe_output_name(symbol)
                    exported.append(
                        generator.export_knowledge_graph(
                            symbol,
                            symbol_root,
                            f"analytical-{store.manifest.source_identity.sha256[:16]}",
                        )
                    )
            return exported, len(exported)

        (manifests, exported_count), metrics = measure(operation)
        completeness = []
        for manifest_path in manifests:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            completeness.append(payload.get("completeness") == "complete")
        files = tuple(
            path
            for path in output_root.rglob("*")
            if path.is_file() and path.name != "dwarf-cache.json"
        )
        return {
            "status": "observed" if exported_count and all(completeness) else "partial",
            **metrics,
            "symbols": list(symbols),
            "manifests": [str(path) for path in manifests],
            "files": len(files),
            "bytes": sum(path.stat().st_size for path in files),
            "sha256": tree_digest(output_root, files),
        }
    except (OSError, RuntimeError, ValueError) as error:
        return {"status": "blocked", "reason": str(error)}


def _build_report(
    store: Any,
    measurements: dict[str, Any],
    baselines: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "partial" if store.manifest.status != "complete" else "observed",
        "source_identity": store.manifest.source_identity.as_fingerprint(),
        "source_path": store.manifest.source_path,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "baseline": {
            "status": _baseline_summary_status(baselines),
            "reason": "Explicit baseline workloads are required for the 110% gate."
            if _baseline_summary_status(baselines) != "observed"
            else None,
        },
        "baselines": baselines,
        "measurements": measurements,
        "runtime_comparison": _runtime_comparison(baselines, measurements),
    }


def _runtime_comparison(baselines: dict[str, Any], measurements: dict[str, Any]) -> dict[str, Any]:
    """Compare serving engines without treating Parquet as a runtime competitor."""
    comparison: dict[str, Any] = {
        "status": "not_observed",
        "baseline_backend": "prior_live_lookup",
        "candidate_backend": "native_doris",
        "excluded_paths": ["parquet_file_store"],
        "queries": [],
    }
    baseline = baselines.get("current_runtime")
    doris = measurements.get("doris")
    if not isinstance(baseline, dict) or not isinstance(doris, dict):
        comparison["reason"] = "Both prior live lookup and native Doris evidence are required."
        return comparison
    if baseline.get("status") != "observed" or doris.get("status") != "observed":
        comparison["reason"] = "Both prior live lookup and native Doris evidence are required."
        return comparison
    baseline_queries = _symbol_queries(baseline.get("queries"))
    doris_queries_by_symbol = _symbol_queries(doris.get("queries"))
    rows = [
        _runtime_comparison_row(symbol, baseline_queries[symbol], doris_queries_by_symbol[symbol])
        for symbol in sorted(baseline_queries.keys() & doris_queries_by_symbol.keys())
    ]
    comparison["queries"] = rows
    comparison["status"] = "observed" if rows else "partial"
    if not rows:
        comparison["reason"] = "No matching find_definitions measurements were observed."
    return comparison


def _symbol_queries(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    return {
        item["symbol"]: item
        for item in value
        if isinstance(item, dict)
        and item.get("query") == "find_definitions"
        and isinstance(item.get("symbol"), str)
    }


def _runtime_comparison_row(
    symbol: str,
    baseline: dict[str, Any],
    doris: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "query": "find_definitions",
        "symbol": symbol,
        "prior_live_lookup": baseline.get("warm"),
        "native_doris": doris.get("warm"),
    }
    baseline_p50 = _warm_percentile(baseline, "p50_seconds")
    doris_p50 = _warm_percentile(doris, "p50_seconds")
    if baseline_p50 is not None and doris_p50 is not None and baseline_p50 > 0:
        row["native_doris_to_prior_p50_ratio"] = doris_p50 / baseline_p50
    baseline_p95 = _warm_percentile(baseline, "p95_seconds")
    doris_p95 = _warm_percentile(doris, "p95_seconds")
    if baseline_p95 is not None and doris_p95 is not None and baseline_p95 > 0:
        row["native_doris_to_prior_p95_ratio"] = doris_p95 / baseline_p95
    return row


def _warm_percentile(query: dict[str, Any], percentile: str) -> float | None:
    warm = query.get("warm")
    if not isinstance(warm, dict):
        return None
    value = warm.get(percentile)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _baseline_measurements(
    elf: Path,
    output_dir: Path,
    symbols: tuple[str, ...],
    iterations: int,
    *,
    run_current_baseline: bool,
) -> dict[str, Any]:
    baselines = _unobserved_baselines()
    if run_current_baseline:
        baselines["current_runtime"] = _safe_baseline(
            lambda: current_runtime_baseline(elf, output_dir, symbols, iterations)
        )
    return baselines


def _unobserved_baselines() -> dict[str, dict[str, str]]:
    return {
        "current_runtime": {
            "status": "not_observed",
            "reason": "Pass --run-current-baseline for the prior live lookup workload.",
        },
    }


def _safe_baseline(factory: Any) -> dict[str, Any]:
    try:
        return factory()
    except (OSError, RuntimeError, ValueError) as error:
        return {"status": "blocked", "reason": str(error)}


def _baseline_summary_status(baselines: dict[str, Any]) -> str:
    statuses = {str(value.get("status")) for value in baselines.values() if isinstance(value, dict)}
    if "blocked" in statuses:
        return "blocked"
    if "observed" in statuses:
        return "observed"
    return "not_observed"


def _doris_measurement(
    manifest_path: Path,
    run_doris: bool,
    query_existing_doris: bool,
    symbols: tuple[str, ...],
    iterations: int,
) -> dict[str, Any]:
    try:
        config = DorisConfig.from_environment()
        plan = build_doris_plan(manifest_path, config)
        if not run_doris and not query_existing_doris:
            return {"status": "not_observed", "plan": plan.to_dict()}
        started = perf_counter()
        result = (
            DorisLoader().execute(plan, config)
            if run_doris
            else {
                "status": "observed",
                "load_status": "not_observed",
                "plan": plan.to_dict(),
            }
        )
        query_started = perf_counter()
        queries = doris_queries(manifest_path, config, symbols, iterations)
        return {
            **result,
            "wall_seconds": perf_counter() - started,
            "query_wall_seconds": perf_counter() - query_started,
            "query_only": query_existing_doris,
            "queries": queries,
        }
    except AnalyticalDependencyError as error:
        return {"status": "unavailable", "reason": str(error)}
    except (OSError, RuntimeError, ValueError) as error:
        return {"status": "blocked", "reason": str(error)}


def _artifact_measurement(manifest_path: Path) -> dict[str, Any]:
    root = manifest_path.resolve().parent
    manifest = load_manifest(manifest_path)
    declared = (
        set(declared_parquet_files(manifest_path, manifest))
        if "parquet" in manifest.files
        else set()
    )
    parquet_root = root / manifest.files.get("parquet", "parquet")
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and (
            "parquet" not in manifest.files
            or not path.is_relative_to(parquet_root)
            or path in declared
        )
    ]
    return {
        "status": "partial" if manifest.status != "complete" else "observed",
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)

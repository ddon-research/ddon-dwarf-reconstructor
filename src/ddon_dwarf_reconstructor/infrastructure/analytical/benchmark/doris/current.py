"""Current-data Doris generation workloads and evidence publication."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .....domain.models.performance import ColdWarmState, EvidenceStatus, PerformanceWorkload
from ....artifacts import SourceIdentityCatalog
from ....performance import PerformanceRunner
from ....performance.workloads import build_reconstructor_workload
from ...doris import DorisConfig
from ...doris_diagnostics import DorisDiagnosticRecorder
from ...doris_store import DorisDwarfStore
from ...manifest import (
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
)
from ..common.metrics import measure
from ..common.output import safe_output_name
from .current_outputs import generation_output as _generation_output
from .queries import doris_queries


def run_current_doris_benchmark(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    *,
    control_symbols: tuple[str, ...] = ("MtObject", "rLayout"),
    control_iterations: int = 1,
    query_iterations: int = 3,
    aifsm_iterations: int = 1,
    control_timeout_seconds: float = 900.0,
    aifsm_timeout_seconds: float = 7200.0,
    sample_interval: float = 1.0,
    doris_cli: Path | None = None,
) -> dict[str, Any]:
    """Benchmark the existing source-bound Doris publication without loading it."""
    _validate_options(
        control_symbols,
        control_iterations,
        query_iterations,
        aifsm_iterations,
        control_timeout_seconds,
        aifsm_timeout_seconds,
        sample_interval,
    )
    output_dir = output_dir.resolve()
    elf, manifest_path, manifest, config = _prepare_inputs(elf, store_manifest, output_dir)

    serving_validation = _validate_doris_serving(manifest_path, elf, config)
    query_contract = _bounded_query_contract(
        manifest_path,
        config,
        (*control_symbols, "rAIFSM"),
        query_iterations,
        output_dir=output_dir,
        doris_cli=doris_cli,
    )
    doris_diagnostics = _load_diagnostics_report(output_dir / "doris-diagnostics")
    runner = PerformanceRunner(output_dir / "profiles", sample_interval_seconds=sample_interval)
    runs = _run_generation_workloads(
        runner,
        elf,
        manifest_path,
        output_dir,
        control_symbols,
        control_iterations,
        control_timeout_seconds,
        aifsm_iterations,
        aifsm_timeout_seconds,
    )
    report = _build_report(
        manifest,
        manifest_path,
        config,
        serving_validation,
        query_contract,
        doris_diagnostics,
        runs,
        control_symbols,
        control_iterations,
        query_iterations,
        control_timeout_seconds,
        aifsm_iterations,
        aifsm_timeout_seconds,
        sample_interval,
        doris_cli,
    )
    _write_report(output_dir / "current-doris-benchmark.json", report)
    return report


def _prepare_inputs(
    elf: Path, store_manifest: Path, output_dir: Path
) -> tuple[Path, Path, Any, DorisConfig]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = store_manifest.resolve()
    elf = elf.resolve()
    manifest = _validate_manifest(elf, manifest_path)
    return elf, manifest_path, manifest, DorisConfig.from_environment()


def _build_report(
    manifest: Any,
    manifest_path: Path,
    config: DorisConfig,
    serving_validation: dict[str, Any],
    query_contract: dict[str, Any],
    doris_diagnostics: dict[str, Any],
    runs: list[dict[str, Any]],
    control_symbols: tuple[str, ...],
    control_iterations: int,
    query_iterations: int,
    control_timeout_seconds: float,
    aifsm_iterations: int,
    aifsm_timeout_seconds: float,
    sample_interval: float,
    doris_cli: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "status": _overall_status(serving_validation, query_contract, doris_diagnostics, runs),
        "workload": "current-doris",
        "backend": _backend_report(config),
        "source_identity": manifest.source_identity.as_fingerprint(),
        "source_path": manifest.source_path,
        "store_manifest": str(manifest_path),
        "store_status": manifest.status,
        "serving_validation": serving_validation,
        "bounded_doris_query_contract": query_contract,
        "doris_diagnostics": doris_diagnostics,
        "workload_configuration": _workload_configuration(
            control_symbols,
            control_iterations,
            query_iterations,
            control_timeout_seconds,
            aifsm_iterations,
            aifsm_timeout_seconds,
            sample_interval,
            doris_cli,
        ),
        "runs": runs,
    }


def _backend_report(config: DorisConfig) -> dict[str, Any]:
    return {
        "type": "native_doris",
        "database": config.database,
        "table": config.table,
        "definition_lookup_table": config.definition_lookup_table,
        "materialize_store": "not_observed",
        "load_store": "not_observed",
    }


def _workload_configuration(
    control_symbols: tuple[str, ...],
    control_iterations: int,
    query_iterations: int,
    control_timeout_seconds: float,
    aifsm_iterations: int,
    aifsm_timeout_seconds: float,
    sample_interval: float,
    doris_cli: Path | None = None,
) -> dict[str, Any]:
    return {
        "control_symbols": list(control_symbols),
        "control_iterations": control_iterations,
        "control_timeout_seconds": control_timeout_seconds,
        "query_iterations": query_iterations,
        "aifsm_symbol": "rAIFSM",
        "aifsm_iterations": aifsm_iterations,
        "aifsm_timeout_seconds": aifsm_timeout_seconds,
        "aifsm_full_hierarchy": True,
        "aifsm_exhaustive": True,
        "sample_interval_seconds": sample_interval,
        "doris_cli": None if doris_cli is None else str(doris_cli.resolve()),
        "diagnostic_scope": "benchmark_suite",
    }


def _validate_options(
    control_symbols: tuple[str, ...],
    control_iterations: int,
    query_iterations: int,
    aifsm_iterations: int,
    control_timeout_seconds: float,
    aifsm_timeout_seconds: float,
    sample_interval: float,
) -> None:
    if not control_symbols:
        raise ValueError("at least one control symbol is required")
    if any(not symbol.strip() for symbol in control_symbols):
        raise ValueError("control symbols must not be empty")
    for name, value in (
        ("control_iterations", control_iterations),
        ("query_iterations", query_iterations),
        ("aifsm_iterations", aifsm_iterations),
    ):
        if value < 1:
            raise ValueError(f"{name} must be positive")
    for name, value in (
        ("control_timeout_seconds", control_timeout_seconds),
        ("aifsm_timeout_seconds", aifsm_timeout_seconds),
        ("sample_interval", sample_interval),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")


def _validate_manifest(elf: Path, manifest_path: Path) -> Any:
    if not elf.is_file():
        raise ValueError(f"ELF does not exist: {elf}")
    manifest = load_manifest(manifest_path)
    if manifest.status != "complete":
        raise ValueError(f"current Doris benchmark requires a complete manifest: {manifest_path}")
    if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
        raise ValueError(
            f"current Doris benchmark requires zero parser diagnostics: {manifest_path}"
        )
    source_identity = SourceIdentityCatalog().identify(elf)
    if source_identity.sha256 != manifest.source_identity.sha256:
        raise ValueError("ELF source identity does not match the supplied analytical manifest")
    return manifest


def _validate_doris_serving(manifest_path: Path, elf: Path, config: DorisConfig) -> dict[str, Any]:
    try:
        started = measure(
            lambda: DorisDwarfStore.load(manifest_path, config=config, source_path=elf)
        )
        store, metrics = started
        registry = store.registry
        store.close()
        if registry is None:
            return {"status": "blocked", "reason": "Doris registry validation returned no snapshot"}
        return {
            "status": "observed",
            **metrics,
            "source_id": registry.source_id,
            "schema_version": registry.schema_version,
            "registry_status": registry.status,
            "expected_counts": registry.expected_counts,
            "observed_counts": registry.observed_counts,
        }
    except (OSError, RuntimeError, ValueError) as error:
        return {"status": "blocked", "reason": str(error)}


def _bounded_query_contract(
    manifest_path: Path,
    config: DorisConfig,
    symbols: tuple[str, ...],
    iterations: int,
    *,
    output_dir: Path,
    doris_cli: Path | None,
) -> dict[str, Any]:
    source_id = load_manifest(manifest_path).source_identity.sha256
    diagnostics = DorisDiagnosticRecorder(
        source_id=source_id,
        config=config,
        artifact_dir=output_dir / "doris-diagnostics",
        manifest_path=manifest_path,
        cli_path=doris_cli,
        scope="benchmark_suite",
    )
    try:
        queries, metrics = measure(
            lambda: doris_queries(
                manifest_path, config, symbols, iterations, diagnostics=diagnostics
            )
        )
        diagnostic_report = diagnostics.finalize()
        return {
            "status": "observed",
            **metrics,
            "semantics": "bounded_first_definition",
            "limit": 1001,
            "symbols": list(symbols),
            "iterations": iterations,
            "queries": queries,
            "diagnostic_status": diagnostic_report["status"],
        }
    except (OSError, RuntimeError, ValueError) as error:
        diagnostic_report = diagnostics.finalize()
        return {
            "status": "blocked",
            "semantics": "bounded_first_definition",
            "symbols": list(symbols),
            "iterations": iterations,
            "reason": str(error),
            "diagnostic_status": diagnostic_report["status"],
        }
    finally:
        diagnostics.finalize()


def _load_diagnostics_report(directory: Path) -> dict[str, Any]:
    path = directory / "doris-diagnostics.json"
    if not path.is_file():
        return {
            "status": "partial",
            "scope": "benchmark_suite",
            "artifact_root": str(directory),
            "reason": "Diagnostic recorder did not publish its manifest.",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        return {
            "status": "partial",
            "scope": "benchmark_suite",
            "artifact_root": str(directory),
            "reason": str(error),
        }
    return (
        payload
        if isinstance(payload, dict)
        else {
            "status": "partial",
            "scope": "benchmark_suite",
            "artifact_root": str(directory),
            "reason": "Diagnostic report is not an object.",
        }
    )


def _run_generation_workloads(
    runner: PerformanceRunner,
    elf: Path,
    manifest_path: Path,
    output_dir: Path,
    control_symbols: tuple[str, ...],
    control_iterations: int,
    control_timeout_seconds: float,
    aifsm_iterations: int,
    aifsm_timeout_seconds: float,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for symbol in control_symbols:
        for state in (ColdWarmState.COLD, ColdWarmState.WARM):
            for iteration in range(1, control_iterations + 1):
                target = (
                    output_dir
                    / "outputs"
                    / safe_output_name(symbol)
                    / state.value
                    / f"{iteration:03d}"
                )
                workload = _generation_workload(
                    elf,
                    manifest_path,
                    target,
                    name=f"current-doris-control-{safe_output_name(symbol)}-{state.value}",
                    symbol=symbol,
                    state=state,
                    timeout_seconds=control_timeout_seconds,
                )
                runs.append(_run_one(runner, workload, target, symbol, state.value, iteration))
    for iteration in range(1, aifsm_iterations + 1):
        target = output_dir / "outputs" / "rAIFSM" / "long" / f"{iteration:03d}"
        workload = _generation_workload(
            elf,
            manifest_path,
            target,
            name="current-doris-raifsm-long",
            symbol="rAIFSM",
            state=ColdWarmState.WARM,
            timeout_seconds=aifsm_timeout_seconds,
            full_hierarchy=True,
            exhaustive=True,
        )
        runs.append(_run_one(runner, workload, target, "rAIFSM", "long", iteration))
    return runs


def _generation_workload(
    elf: Path,
    manifest_path: Path,
    target: Path,
    *,
    name: str,
    symbol: str,
    state: ColdWarmState,
    timeout_seconds: float,
    full_hierarchy: bool = False,
    exhaustive: bool = False,
) -> PerformanceWorkload:
    return build_reconstructor_workload(
        repository_root=Path.cwd(),
        name=name,
        elf=elf,
        symbols=(symbol,),
        mode="generate",
        state=state,
        output_dir=target,
        dwarf_store_manifest=manifest_path,
        full_hierarchy=full_hierarchy,
        exhaustive=exhaustive,
        timeout_seconds=timeout_seconds,
    )


def _run_one(
    runner: PerformanceRunner,
    workload: PerformanceWorkload,
    target: Path,
    symbol: str,
    state: str,
    iteration: int,
) -> dict[str, Any]:
    try:
        summary = runner.run(workload)
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "status": "blocked",
            "symbol": symbol,
            "state": state,
            "iteration": iteration,
            "workload": workload.to_dict(),
            "reason": str(error),
        }
    output = _generation_output(target)
    status = _run_status(summary.status.value, output["status"])
    return {
        "status": status,
        "symbol": symbol,
        "state": state,
        "iteration": iteration,
        "workload": workload.to_dict(),
        "run": summary.to_dict(),
        "output": output,
    }


def _run_status(summary_status: str, output_status: str) -> str:
    if summary_status == EvidenceStatus.OBSERVED.value and output_status == "observed":
        return "observed"
    if summary_status == EvidenceStatus.BLOCKED.value:
        return "blocked"
    return "partial"


def _overall_status(*sections: dict[str, Any] | list[dict[str, Any]]) -> str:
    statuses: list[str] = []
    for section in sections:
        values = section if isinstance(section, list) else [section]
        statuses.extend(str(item.get("status")) for item in values if isinstance(item, dict))
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses:
        return "partial"
    return (
        "observed"
        if statuses and all(status == "observed" for status in statuses)
        else "not_observed"
    )


def _write_report(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


__all__ = ["run_current_doris_benchmark"]

"""Generation-child workload construction for the current Doris benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .....domain.models.performance import ColdWarmState, EvidenceStatus, PerformanceWorkload
from ....performance import PerformanceRunner
from ....performance.workloads import build_reconstructor_workload
from ..common.output import safe_output_name
from .current_outputs import generation_output as _generation_output


def run_generation_workloads(
    runner: PerformanceRunner,
    elf: Path,
    manifest_path: Path,
    output_dir: Path,
    control_symbols: tuple[str, ...],
    control_iterations: int,
    control_timeout_seconds: float,
    aifsm_iterations: int,
    aifsm_timeout_seconds: float,
    control_cold_iterations: int | None,
    control_warm_iterations: int | None,
    aifsm_cold_iterations: int,
    trace_generation_queries: bool,
    trace_profile_threshold_ms: float,
    trace_max_profiles: int,
) -> list[dict[str, Any]]:
    """Run control symbols and the heavy exhaustive rAIFSM workload."""
    runs = _run_control_workloads(
        runner,
        elf,
        manifest_path,
        output_dir,
        control_symbols,
        control_iterations,
        control_timeout_seconds,
        control_cold_iterations,
        control_warm_iterations,
        trace_generation_queries,
        trace_profile_threshold_ms,
        trace_max_profiles,
    )
    runs.extend(
        _run_aifsm_workloads(
            runner,
            elf,
            manifest_path,
            output_dir,
            aifsm_iterations,
            aifsm_timeout_seconds,
            aifsm_cold_iterations,
            trace_generation_queries,
            trace_profile_threshold_ms,
            trace_max_profiles,
        )
    )
    return runs


def _run_control_workloads(
    runner: PerformanceRunner,
    elf: Path,
    manifest_path: Path,
    output_dir: Path,
    symbols: tuple[str, ...],
    default_iterations: int,
    timeout_seconds: float,
    cold_iterations: int | None,
    warm_iterations: int | None,
    trace_generation_queries: bool,
    trace_profile_threshold_ms: float,
    trace_max_profiles: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for symbol in symbols:
        for state in (ColdWarmState.COLD, ColdWarmState.WARM):
            iterations = (
                cold_iterations if state == ColdWarmState.COLD else warm_iterations
            ) or default_iterations
            for iteration in range(1, iterations + 1):
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
                    timeout_seconds=timeout_seconds,
                    query_trace_path=_trace_path(target, trace_generation_queries),
                    query_trace_profile_threshold_ms=trace_profile_threshold_ms,
                    query_trace_max_profiles=trace_max_profiles,
                )
                runs.append(_run_one(runner, workload, target, symbol, state.value, iteration))
    return runs


def _run_aifsm_workloads(
    runner: PerformanceRunner,
    elf: Path,
    manifest_path: Path,
    output_dir: Path,
    warm_iterations: int,
    timeout_seconds: float,
    cold_iterations: int,
    trace_generation_queries: bool,
    trace_profile_threshold_ms: float,
    trace_max_profiles: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for state, iterations, state_name in (
        (ColdWarmState.COLD, cold_iterations, "cold"),
        (ColdWarmState.WARM, warm_iterations, "long"),
    ):
        for iteration in range(1, iterations + 1):
            target = output_dir / "outputs" / "rAIFSM" / state_name / f"{iteration:03d}"
            workload = _generation_workload(
                elf,
                manifest_path,
                target,
                name=f"current-doris-raifsm-{state_name}",
                symbol="rAIFSM",
                state=state,
                timeout_seconds=timeout_seconds,
                full_hierarchy=True,
                exhaustive=True,
                query_trace_path=_trace_path(target, trace_generation_queries),
                query_trace_profile_threshold_ms=trace_profile_threshold_ms,
                query_trace_max_profiles=trace_max_profiles,
            )
            runs.append(_run_one(runner, workload, target, "rAIFSM", state_name, iteration))
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
    query_trace_path: Path | None = None,
    query_trace_profile_threshold_ms: float = 500.0,
    query_trace_max_profiles: int = 20,
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
        query_trace_path=query_trace_path,
        query_trace_profile_threshold_ms=query_trace_profile_threshold_ms,
        query_trace_max_profiles=query_trace_max_profiles,
    )


def _trace_path(target: Path, enabled: bool) -> Path | None:
    return target / "doris-query-trace.jsonl" if enabled else None


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
    query_trace = _load_query_trace(target / "doris-query-trace.json")
    if query_trace.get("status") in {"partial", "blocked"} and status != "blocked":
        status = "partial"
    return {
        "status": status,
        "symbol": symbol,
        "state": state,
        "iteration": iteration,
        "workload": workload.to_dict(),
        "run": summary.to_dict(),
        "output": output,
        "query_trace": query_trace,
    }


def _run_status(summary_status: str, output_status: str) -> str:
    if summary_status == EvidenceStatus.OBSERVED.value and output_status == "observed":
        return "observed"
    if summary_status == EvidenceStatus.BLOCKED.value:
        return "blocked"
    return "partial"


def _load_query_trace(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "not_observed", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        return {"status": "partial", "path": str(path), "reason": str(error)}
    if isinstance(payload, dict):
        return payload
    return {
        "status": "partial",
        "path": str(path),
        "reason": "Query trace summary is not an object.",
    }


__all__ = ["run_generation_workloads"]

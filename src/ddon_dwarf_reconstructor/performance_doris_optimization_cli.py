"""CLI command for the opt-in Doris optimization evaluation matrix."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def benchmark_doris_optimization(
    elf: Path = typer.Argument(..., help="ELF whose identity must match the live Doris registry."),
    store_manifest: Path = typer.Option(
        ..., "--store-manifest", help="Complete manifest already published in live Doris."
    ),
    output_dir: Path = typer.Option(..., "--output-dir", help="External benchmark artifact root."),
    candidate: str = typer.Option(
        "canonical",
        "--candidate",
        help="Canonical baseline or an explicitly provisionable lookup candidate.",
    ),
    provision_candidate: bool = typer.Option(
        False,
        "--provision-candidate",
        help="Create and populate an isolated source-bound lookup candidate before measuring it.",
    ),
    control_symbol: list[str] = typer.Option(
        ["MtObject", "rLayout"], "--control-symbol", help="Short generation control symbol."
    ),
    control_cold_iterations: int = typer.Option(3, "--control-cold-iterations", min=1, max=20),
    control_warm_iterations: int = typer.Option(5, "--control-warm-iterations", min=1, max=20),
    query_iterations: int = typer.Option(5, "--query-iterations", min=1, max=20),
    aifsm_cold_iterations: int = typer.Option(1, "--aifsm-cold-iterations", min=0, max=20),
    aifsm_iterations: int = typer.Option(3, "--aifsm-iterations", min=1, max=20),
    control_timeout_seconds: float = typer.Option(900.0, "--control-timeout-seconds", min=0.1),
    aifsm_timeout_seconds: float = typer.Option(7200.0, "--aifsm-timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(1.0, "--sample-interval", min=0.01),
    trace_generation_queries: bool = typer.Option(
        False,
        "--trace-generation-queries",
        help="Capture bounded redacted observations from each generation child.",
    ),
    trace_profile_threshold_ms: float = typer.Option(
        500.0, "--trace-profile-threshold-ms", min=0.1
    ),
    trace_max_profiles: int = typer.Option(20, "--trace-max-profiles", min=1, max=1000),
    doris_cli: Path | None = typer.Option(
        None, "--doris-cli", help="Optional doriscli executable for profile retrieval."
    ),
) -> None:
    """Run current-Doris evidence plus the isolated optimization candidate matrix."""
    from .infrastructure.analytical.benchmark import run_doris_optimization_benchmark

    report = run_doris_optimization_benchmark(
        elf,
        store_manifest,
        output_dir,
        candidate_id=candidate,
        provision_candidate=provision_candidate,
        control_symbols=tuple(control_symbol),
        control_cold_iterations=control_cold_iterations,
        control_warm_iterations=control_warm_iterations,
        query_iterations=query_iterations,
        aifsm_cold_iterations=aifsm_cold_iterations,
        aifsm_iterations=aifsm_iterations,
        control_timeout_seconds=control_timeout_seconds,
        aifsm_timeout_seconds=aifsm_timeout_seconds,
        sample_interval=sample_interval,
        doris_cli=doris_cli,
        trace_generation_queries=trace_generation_queries,
        trace_profile_threshold_ms=trace_profile_threshold_ms,
        trace_max_profiles=trace_max_profiles,
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


__all__ = ["benchmark_doris_optimization"]

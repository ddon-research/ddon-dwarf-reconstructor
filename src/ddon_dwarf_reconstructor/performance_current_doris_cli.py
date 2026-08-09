"""CLI command for benchmarking the existing live Doris publication."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def benchmark_doris_current(
    elf: Path = typer.Argument(..., help="ELF whose identity must match the live Doris registry."),
    store_manifest: Path = typer.Option(
        ..., "--store-manifest", help="Complete manifest already published in live Doris."
    ),
    output_dir: Path = typer.Option(..., "--output-dir", help="External benchmark artifact root."),
    control_symbol: list[str] = typer.Option(
        ["MtObject", "rLayout"],
        "--control-symbol",
        help="Short generate control; repeat as needed. rAIFSM is always measured separately.",
    ),
    control_iterations: int = typer.Option(1, "--control-iterations", min=1, max=20),
    query_iterations: int = typer.Option(3, "--query-iterations", min=1, max=20),
    aifsm_iterations: int = typer.Option(1, "--aifsm-iterations", min=1, max=20),
    control_timeout_seconds: float = typer.Option(900.0, "--control-timeout-seconds", min=0.1),
    aifsm_timeout_seconds: float = typer.Option(7200.0, "--aifsm-timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(1.0, "--sample-interval", min=0.01),
    doris_cli: Path | None = typer.Option(
        None,
        "--doris-cli",
        help="Optional doriscli executable used for explain and profile retrieval.",
    ),
) -> None:
    """Benchmark current native Doris data without materializing or loading it."""
    from .infrastructure.analytical.benchmark import run_current_doris_benchmark

    report = run_current_doris_benchmark(
        elf,
        store_manifest,
        output_dir,
        control_symbols=tuple(control_symbol),
        control_iterations=control_iterations,
        query_iterations=query_iterations,
        aifsm_iterations=aifsm_iterations,
        control_timeout_seconds=control_timeout_seconds,
        aifsm_timeout_seconds=aifsm_timeout_seconds,
        sample_interval=sample_interval,
        doris_cli=doris_cli,
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


__all__ = ["benchmark_doris_current"]

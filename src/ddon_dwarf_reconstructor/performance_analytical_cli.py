"""Typer command and workload helpers for analytical-store profiling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from .domain.models.performance import (
    ColdWarmState,
    PerformanceWorkload,
    RunSummary,
)
from .infrastructure.performance import (
    PerformanceRunner,
    get_performance_artifact_dir,
    get_performance_database_path,
)
from .infrastructure.performance.history import HistoryStore
from .infrastructure.performance.profilers import PerformanceProfiler


def profile_dwarf_store(
    elf: Path = typer.Argument(..., help="ELF file associated with the store."),
    output_dir: Path = typer.Option(..., "--output-dir", help="External benchmark artifact root."),
    store_manifest: Path | None = typer.Option(None, "--store-manifest"),
    symbol: list[str] = typer.Option(
        ["MtObject", "rLayout"], "--symbol", "-s", help="Definition query; repeat as needed."
    ),
    run_doris: bool = typer.Option(False, "--run-doris"),
    query_existing_doris: bool = typer.Option(False, "--query-existing-doris"),
    iterations: int = typer.Option(3, "--iterations", min=1, max=20),
    allow_incomplete: bool = typer.Option(False, "--allow-incomplete"),
    run_knowledge_export: bool = typer.Option(False, "--run-knowledge-export"),
    profiler: list[str] = typer.Option(
        [],
        "--profiler",
        help="Profiler: scalene, scalene-libraries, cprofile, pyinstrument, py-spy, or tracemalloc; repeat or use all.",
    ),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir"),
    history_db: Path | None = typer.Option(None, "--history-db"),
    timeout_seconds: float = typer.Option(300.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.1, "--sample-interval", min=0.01),
) -> None:
    """Profile the bounded analytical-store benchmark through the shared runner."""
    if not profiler:
        raise typer.BadParameter(
            "provide at least one --profiler (for example scalene or cprofile)"
        )
    if run_doris and query_existing_doris:
        raise typer.BadParameter("--run-doris and --query-existing-doris are mutually exclusive")
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    command = benchmark_dwarf_store_command(
        elf=elf,
        output_dir=output_dir,
        store_manifest=store_manifest,
        symbols=tuple(symbol),
        run_doris=run_doris,
        query_existing_doris=query_existing_doris,
        iterations=iterations,
        allow_incomplete=allow_incomplete,
        run_knowledge_export=run_knowledge_export,
    )
    workload = PerformanceWorkload(
        name="analytical-dwarf-store-profile",
        command=tuple(command),
        cwd=repository_root,
        state=ColdWarmState.WARM,
        timeout_seconds=timeout_seconds,
        source_path=elf,
        configuration=(
            ("store_manifest", str(store_manifest or "")),
            ("symbols", ",".join(symbol)),
            ("query_existing_doris", str(query_existing_doris).lower()),
        ),
    )
    summaries = profile_workload(workload, raw_root, history_db, sample_interval, tuple(profiler))
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


def profile_workload(
    workload: PerformanceWorkload,
    artifact_root: Path,
    history_db: Path | None,
    sample_interval: float,
    profilers: tuple[str, ...],
) -> tuple[RunSummary, ...]:
    """Run profilers around a workload and persist each result in history."""
    runner = PerformanceRunner(artifact_root, sample_interval_seconds=sample_interval)
    summaries = PerformanceProfiler(runner).profile(workload, profilers)
    store = HistoryStore(history_db or get_performance_database_path(workload.cwd))
    for summary in summaries:
        store.record(summary)
    return summaries


def benchmark_dwarf_store_command(
    *,
    elf: Path,
    output_dir: Path,
    store_manifest: Path | None,
    symbols: tuple[str, ...],
    run_doris: bool,
    query_existing_doris: bool,
    iterations: int,
    allow_incomplete: bool,
    run_knowledge_export: bool,
) -> list[str]:
    """Build the unprofiled child command for the analytical benchmark."""
    command = [
        sys.executable,
        "-m",
        "ddon_dwarf_reconstructor",
        "performance",
        "benchmark-dwarf-store",
        str(elf),
        "--output-dir",
        str(output_dir),
        "--iterations",
        str(iterations),
    ]
    for item in symbols:
        command.extend(("--symbol", item))
    if store_manifest is not None:
        command.extend(("--store-manifest", str(store_manifest)))
    for enabled, option in (
        (run_doris, "--run-doris"),
        (query_existing_doris, "--query-existing-doris"),
        (allow_incomplete, "--allow-incomplete"),
        (run_knowledge_export, "--run-knowledge-export"),
    ):
        if enabled:
            command.append(option)
    return command


_benchmark_dwarf_store_command = benchmark_dwarf_store_command


__all__ = [
    "_benchmark_dwarf_store_command",
    "benchmark_dwarf_store_command",
    "profile_dwarf_store",
    "profile_workload",
]

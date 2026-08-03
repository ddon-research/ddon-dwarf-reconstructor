"""Typer commands for opt-in profiling and historical benchmark evidence."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import typer

from .domain.models.performance import ColdWarmState, PerformanceWorkload, RunSummary
from .infrastructure.performance import (
    PerformanceRunner,
    discover_tools,
    get_performance_artifact_dir,
    get_performance_database_path,
)
from .infrastructure.performance.export import export_history
from .infrastructure.performance.history import HistoryStore
from .infrastructure.performance.profilers import PerformanceProfiler
from .infrastructure.performance.workloads import (
    build_dump_index_workload,
    build_fixture_workload,
    build_reconstructor_workload,
)

app = typer.Typer(
    name="performance",
    help="Collect opt-in CPU, memory, I/O, and profiler evidence.",
    no_args_is_help=True,
)
history_app = typer.Typer(
    name="history",
    help="Compare and export the tracked benchmark history.",
    no_args_is_help=True,
)
app.add_typer(history_app, name="history")


@app.command()
def doctor() -> None:
    """Report available profiling tools and evidence paths as JSON."""
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "artifact_dir": str(get_performance_artifact_dir()),
        "history_db": str(get_performance_database_path()),
        "tools": [tool.to_dict() for tool in discover_tools()],
        "boundary": {
            "raw_profiles": "external_os_artifact_dir",
            "real_asset_ci": "not_required",
            "memray_windows": "not_supported",
        },
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command()
def profile(
    elf: Path = typer.Argument(..., help="ELF file to analyze."),
    symbol: list[str] = typer.Option([], "--symbol", "-s", help="Symbol; repeat as needed."),
    symbols_file: Path | None = typer.Option(None, "--symbols-file"),
    mode: str = typer.Option(
        "export-knowledge", help="Canonical command: generate or export-knowledge."
    ),
    state: ColdWarmState = typer.Option(ColdWarmState.WARM, help="Measured cache state."),
    profiler: list[str] = typer.Option([], "--profiler", help="Profiler; repeat or use all."),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Target command output directory."
    ),
    artifact_dir: Path | None = typer.Option(
        None, "--artifact-dir", help="External raw evidence root."
    ),
    history_db: Path | None = typer.Option(None, "--history-db"),
    dwarf_dump: Path | None = typer.Option(None, "--dwarf-dump"),
    dwarf_index: Path | None = typer.Option(None, "--dwarf-index"),
    build_id: str | None = typer.Option(None, "--build-id"),
    orbis_objdump: Path | None = typer.Option(None, "--orbis-objdump"),
    full_hierarchy: bool = typer.Option(False, "--full-hierarchy"),
    single_file: bool = typer.Option(False, "--single-file"),
    exhaustive: bool = typer.Option(False, "--exhaustive"),
    resolve_param_names: bool = typer.Option(False, "--resolve-param-names"),
    timeout_seconds: float = typer.Option(300.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.1, "--sample-interval", min=0.01),
    name: str = typer.Option("reconstructor", "--name"),
) -> None:
    """Profile the canonical generate or export-knowledge command."""
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    target_output = output_dir or raw_root / name / "target-output"
    workload = build_reconstructor_workload(
        repository_root=repository_root,
        name=name,
        elf=elf,
        symbols=tuple(symbol),
        mode=mode,
        state=state,
        output_dir=target_output,
        dwarf_dump=dwarf_dump,
        dwarf_index=dwarf_index,
        build_id=build_id,
        orbis_objdump=orbis_objdump,
        symbols_file=symbols_file,
        full_hierarchy=full_hierarchy,
        single_file=single_file,
        exhaustive=exhaustive,
        resolve_param_names=resolve_param_names,
        timeout_seconds=timeout_seconds,
    )
    summaries = _profile_workload(workload, raw_root, history_db, sample_interval, tuple(profiler))
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


@app.command("profile-index")
def profile_index(
    dwarf_dump: Path = typer.Argument(..., help="Compressed LLVM DWARF dump to index."),
    index_path: Path | None = typer.Option(None, "--index-path"),
    state: ColdWarmState = typer.Option(ColdWarmState.COLD, help="Measured cache state."),
    profiler: list[str] = typer.Option([], "--profiler", help="Profiler; repeat or use all."),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir"),
    history_db: Path | None = typer.Option(None, "--history-db"),
    timeout_seconds: float = typer.Option(3600.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(1.0, "--sample-interval", min=0.01),
    name: str = typer.Option("cold-dump-index", "--name"),
) -> None:
    """Profile one complete streaming compressed-dump index rebuild."""
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    workload = build_dump_index_workload(
        repository_root=repository_root,
        name=name,
        dwarf_dump=dwarf_dump,
        index_path=index_path,
        state=state,
        timeout_seconds=timeout_seconds,
    )
    selected_profilers = tuple(profiler) or ("process-sampler",)
    summaries = _profile_workload(
        workload, raw_root, history_db, sample_interval, selected_profilers
    )
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


@app.command()
def benchmark(
    name: str = typer.Option("fixture", "--name"),
    iterations: int = typer.Option(1, "--iterations", min=1, max=20),
    state: ColdWarmState = typer.Option(ColdWarmState.WARM),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir"),
    history_db: Path | None = typer.Option(None, "--history-db"),
    timeout_seconds: float = typer.Option(30.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.05, "--sample-interval", min=0.01),
) -> None:
    """Run the deterministic fixture benchmark and record every iteration."""
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    store = HistoryStore(history_db or get_performance_database_path(repository_root))
    runner = PerformanceRunner(raw_root, sample_interval_seconds=sample_interval)
    summaries = []
    for _iteration in range(iterations):
        workload = build_fixture_workload(
            repository_root=repository_root,
            name=name,
            state=state,
            timeout_seconds=timeout_seconds,
        )
        summary = PerformanceProfiler(runner).profile(workload, ("pyperf",))[0]
        store.record(summary)
        summaries.append(summary)
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


@history_app.command("compare")
def compare_history(
    workload: str | None = typer.Option(None, "--workload"),
    run_id: str | None = typer.Option(None, "--run-id"),
    history_db: Path | None = typer.Option(None, "--history-db"),
) -> None:
    """Compare the latest compatible history rows."""
    store = HistoryStore(history_db or get_performance_database_path())
    typer.echo(
        json.dumps(store.compare(workload=workload, run_id=run_id), indent=2, sort_keys=True)
    )


@history_app.command("export")
def export_history_command(
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    markdown_path: Path | None = typer.Option(None, "--markdown-path"),
    workload: str | None = typer.Option(None, "--workload"),
    history_db: Path | None = typer.Option(None, "--history-db"),
) -> None:
    """Export deterministic JSON, CSV, and static Markdown history."""
    repository_root = Path.cwd()
    store = HistoryStore(history_db or get_performance_database_path(repository_root))
    target_dir = output_dir or repository_root / "resources" / "performance"
    target_markdown = (
        markdown_path
        or repository_root / "docs" / "knowledge-base" / "performance" / "benchmark-history.md"
    )
    paths = export_history(store, target_dir, markdown_path=target_markdown, workload=workload)
    typer.echo(
        json.dumps(
            {"json": str(paths[0]), "csv": str(paths[1]), "markdown": str(paths[2])}, indent=2
        )
    )


def _profile_workload(
    workload: PerformanceWorkload,
    artifact_root: Path,
    history_db: Path | None,
    sample_interval: float,
    profilers: tuple[str, ...],
) -> tuple[RunSummary, ...]:
    runner = PerformanceRunner(artifact_root, sample_interval_seconds=sample_interval)
    summaries = PerformanceProfiler(runner).profile(workload, profilers)
    store = HistoryStore(history_db or get_performance_database_path(workload.cwd))
    for summary in summaries:
        store.record(summary)
    return summaries


__all__ = ["app"]

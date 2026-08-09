"""Typer commands for opt-in profiling and historical benchmark evidence."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import typer

from .domain.models.performance import (
    ColdWarmState,
    EvidenceStatus,
    RunSummary,
    RuntimeDescriptor,
)
from .infrastructure.performance import (
    PerformanceRunner,
    discover_tools,
    get_performance_artifact_dir,
    get_performance_database_path,
)
from .infrastructure.performance.export import export_history
from .infrastructure.performance.history import HistoryStore
from .infrastructure.performance.profilers import PerformanceProfiler
from .infrastructure.performance.runtime import (
    current_runtime,
    ensure_project_importable,
    nuitka_runtime,
    probe_python_runtime,
)
from .infrastructure.performance.workloads import (
    build_dump_index_workload,
    build_fixture_workload,
    build_reconstructor_workload,
)
from .performance_analytical_cli import (
    profile_dwarf_store,
)
from .performance_analytical_cli import (
    profile_workload as _profile_workload,
)
from .performance_current_doris_cli import benchmark_doris_current
from .performance_materializer_cli import profile_materializer

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
app.command("profile-dwarf-store")(profile_dwarf_store)
app.command("profile-materializer")(profile_materializer)
app.command("benchmark-doris-current")(benchmark_doris_current)


@app.command()
def doctor() -> None:
    """Report available profiling tools and evidence paths as JSON."""
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runtime": current_runtime().to_dict(),
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
    profiler: list[str] = typer.Option(
        [],
        "--profiler",
        help="Profiler: scalene, scalene-libraries, cprofile, pyinstrument, py-spy, or tracemalloc; repeat or use all.",
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Target command output directory."
    ),
    artifact_dir: Path | None = typer.Option(
        None, "--artifact-dir", help="External raw evidence root."
    ),
    history_db: Path | None = typer.Option(None, "--history-db"),
    dwarf_dump: Path | None = typer.Option(None, "--dwarf-dump"),
    dwarf_index: Path | None = typer.Option(None, "--dwarf-index"),
    dwarf_store_manifest: Path | None = typer.Option(None, "--dwarf-store"),
    build_id: str | None = typer.Option(None, "--build-id"),
    orbis_objdump: Path | None = typer.Option(None, "--orbis-objdump"),
    full_hierarchy: bool = typer.Option(False, "--full-hierarchy"),
    single_file: bool = typer.Option(False, "--single-file"),
    exhaustive: bool = typer.Option(False, "--exhaustive"),
    resolve_param_names: bool = typer.Option(False, "--resolve-param-names"),
    python_executable: Path | None = typer.Option(
        None, "--python-executable", help="Alternate CPython executable for the workload."
    ),
    launcher: Path | None = typer.Option(
        None, "--launcher", help="Compiled application executable for the workload."
    ),
    timeout_seconds: float = typer.Option(300.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.1, "--sample-interval", min=0.01),
    name: str = typer.Option("reconstructor", "--name"),
) -> None:
    """Profile the canonical generate or export-knowledge command."""
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    runtime = _runtime_for_selection(python_executable, launcher)
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
        dwarf_store_manifest=dwarf_store_manifest,
        build_id=build_id,
        orbis_objdump=orbis_objdump,
        symbols_file=symbols_file,
        full_hierarchy=full_hierarchy,
        single_file=single_file,
        exhaustive=exhaustive,
        resolve_param_names=resolve_param_names,
        timeout_seconds=timeout_seconds,
        python_executable=python_executable,
        launcher=launcher,
        runtime=runtime,
    )
    summaries = _profile_workload(workload, raw_root, history_db, sample_interval, tuple(profiler))
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


@app.command("compare-runtimes")
def compare_runtimes(
    elf: Path = typer.Argument(..., help="ELF file to analyze."),
    nuitka_executable: Path = typer.Option(..., "--nuitka-executable"),
    free_threaded_python: Path | None = typer.Option(None, "--free-threaded-python"),
    symbol: list[str] = typer.Option(["rLayout"], "--symbol", "-s"),
    dwarf_store_manifest: Path | None = typer.Option(None, "--dwarf-store"),
    build_id: str | None = typer.Option(None, "--build-id"),
    iterations: int = typer.Option(3, "--iterations", min=1, max=10),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir"),
    history_db: Path | None = typer.Option(None, "--history-db"),
    timeout_seconds: float = typer.Option(300.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.2, "--sample-interval", min=0.01),
) -> None:
    """Compare CPython, a Nuitka launcher, and optional free-threaded CPython."""
    repository_root = Path.cwd()
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    store = HistoryStore(history_db or get_performance_database_path(repository_root))
    host = current_runtime()
    _validate_runtime_paths(nuitka_executable, free_threaded_python)
    selections = _runtime_selections(host, free_threaded_python, repository_root, nuitka_executable)
    summaries = _run_runtime_selections(
        selections=selections,
        iterations=iterations,
        runner=PerformanceRunner(raw_root, sample_interval_seconds=sample_interval),
        store=store,
        repository_root=repository_root,
        elf=elf,
        symbols=tuple(symbol),
        dwarf_store_manifest=dwarf_store_manifest,
        build_id=build_id,
        timeout_seconds=timeout_seconds,
        raw_root=raw_root,
    )
    typer.echo(_runtime_comparison_json(summaries))


def _validate_runtime_paths(nuitka_executable: Path, free_threaded_python: Path | None) -> None:
    if not nuitka_executable.is_file():
        raise typer.BadParameter(f"Nuitka executable does not exist: {nuitka_executable}")
    if free_threaded_python is not None and not free_threaded_python.is_file():
        raise typer.BadParameter(
            f"free-threaded Python executable does not exist: {free_threaded_python}"
        )


def _runtime_selections(
    host: RuntimeDescriptor,
    free_threaded_python: Path | None,
    repository_root: Path,
    nuitka_executable: Path,
) -> list[tuple[str, Path | None, Path | None, RuntimeDescriptor]]:
    selections: list[tuple[str, Path | None, Path | None, RuntimeDescriptor]] = [
        ("cpython", None, None, host),
        ("nuitka", None, nuitka_executable, nuitka_runtime(nuitka_executable, host.python_version)),
    ]
    if free_threaded_python is not None:
        selections.append(
            (
                "free-threaded",
                free_threaded_python,
                None,
                _free_threaded_runtime(free_threaded_python, repository_root),
            )
        )
    return selections


def _free_threaded_runtime(executable: Path, repository_root: Path) -> RuntimeDescriptor:
    try:
        ensure_project_importable(executable, repository_root)
        return probe_python_runtime(executable)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _run_runtime_selections(
    *,
    selections: list[tuple[str, Path | None, Path | None, RuntimeDescriptor]],
    iterations: int,
    runner: PerformanceRunner,
    store: HistoryStore,
    repository_root: Path,
    elf: Path,
    symbols: tuple[str, ...],
    dwarf_store_manifest: Path | None,
    build_id: str | None,
    timeout_seconds: float,
    raw_root: Path,
) -> list[RunSummary]:
    summaries: list[RunSummary] = []
    for selection in selections:
        summaries.extend(
            _run_runtime_selection(
                selection=selection,
                iterations=iterations,
                runner=runner,
                store=store,
                repository_root=repository_root,
                elf=elf,
                symbols=symbols,
                dwarf_store_manifest=dwarf_store_manifest,
                build_id=build_id,
                timeout_seconds=timeout_seconds,
                raw_root=raw_root,
            )
        )
    return summaries


def _run_runtime_selection(
    *,
    selection: tuple[str, Path | None, Path | None, RuntimeDescriptor],
    iterations: int,
    runner: PerformanceRunner,
    store: HistoryStore,
    repository_root: Path,
    elf: Path,
    symbols: tuple[str, ...],
    dwarf_store_manifest: Path | None,
    build_id: str | None,
    timeout_seconds: float,
    raw_root: Path,
) -> list[RunSummary]:
    label, python_executable, launcher, runtime = selection
    summaries: list[RunSummary] = []
    for _iteration in range(1, iterations + 1):
        name = f"runtime-compare-{label}"
        workload = build_reconstructor_workload(
            repository_root=repository_root,
            name=name,
            elf=elf,
            symbols=symbols,
            mode="export-knowledge",
            state=ColdWarmState.WARM,
            output_dir=raw_root / name / "target-output",
            dwarf_store_manifest=dwarf_store_manifest,
            build_id=build_id,
            timeout_seconds=timeout_seconds,
            python_executable=python_executable,
            launcher=launcher,
            runtime=runtime,
        )
        summary = runner.run(workload)
        store.record(summary)
        summaries.append(summary)
    return summaries


def _runtime_comparison_json(summaries: list[RunSummary]) -> str:
    return json.dumps(
        {
            "runs": [summary.to_dict() for summary in summaries],
            "comparisons": _runtime_comparisons(summaries),
        },
        indent=2,
        sort_keys=True,
    )


@app.command("profile-index")
def profile_index(
    dwarf_dump: Path = typer.Argument(..., help="Compressed LLVM DWARF dump to index."),
    index_path: Path | None = typer.Option(None, "--index-path"),
    state: ColdWarmState = typer.Option(ColdWarmState.COLD, help="Measured cache state."),
    profiler: list[str] = typer.Option(
        [],
        "--profiler",
        help="Profiler: scalene, scalene-libraries, cprofile, pyinstrument, py-spy, or tracemalloc; repeat or use all.",
    ),
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


@app.command("benchmark-dwarf-store")
def benchmark_dwarf_store(
    elf: Path = typer.Argument(..., help="ELF file to materialize or benchmark."),
    output_dir: Path = typer.Option(..., "--output-dir", help="External benchmark artifact root."),
    store_manifest: Path | None = typer.Option(None, "--store-manifest"),
    symbol: list[str] = typer.Option(
        ["MtObject", "rLayout"], "--symbol", "-s", help="Definition query; repeat as needed."
    ),
    run_doris: bool = typer.Option(False, "--run-doris", help="Execute the Doris load plan."),
    query_existing_doris: bool = typer.Option(
        False,
        "--query-existing-doris",
        help="Query an already-loaded native Doris projection without reloading it.",
    ),
    iterations: int = typer.Option(3, "--iterations", min=1, max=20),
    run_current_baseline: bool = typer.Option(
        False,
        "--run-current-baseline",
        help="Measure the pre-store live pyelftools lookup path.",
    ),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help="Run diagnostic file queries against an explicit checkpoint snapshot.",
    ),
    run_knowledge_export: bool = typer.Option(
        False,
        "--run-knowledge-export",
        help="Measure complete store-backed knowledge export and hash its outputs.",
    ),
) -> None:
    """Benchmark one-pass materialization and available analytical projections."""
    from .infrastructure.analytical.benchmark import run_store_benchmark

    report = run_store_benchmark(
        elf,
        output_dir,
        store_manifest=store_manifest,
        symbols=tuple(symbol),
        run_doris=run_doris,
        iterations=iterations,
        query_existing_doris=query_existing_doris,
        run_current_baseline=run_current_baseline,
        allow_incomplete=allow_incomplete,
        run_knowledge_export=run_knowledge_export,
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("benchmark-doris-flight")
def benchmark_doris_flight(
    store_manifest: Path = typer.Option(
        ..., "--store-manifest", help="Complete source-bound manifest already loaded in Doris."
    ),
    output_dir: Path = typer.Option(..., "--output-dir", help="External benchmark artifact root."),
    symbol: list[str] = typer.Option(
        ["MtObject", "rLayout"], "--symbol", "-s", help="Definition query; repeat as needed."
    ),
    iterations: int = typer.Option(3, "--iterations", min=1, max=20),
    include_mysql: bool = typer.Option(
        True,
        "--include-mysql/--flight-only",
        help="Run the PyMySQL row baseline alongside Flight SQL.",
    ),
    allow_unparameterized_fallback: bool = typer.Option(
        False,
        "--allow-unparameterized-flight-fallback/--no-unparameterized-flight-fallback",
        help="Render checked SQL literals when Doris rejects Flight parameter upload.",
    ),
    include_cold_connections: bool = typer.Option(
        True,
        "--include-cold-connections/--reused-connections-only",
        help="Include expensive fresh Flight connection samples in every query shape.",
    ),
) -> None:
    """Compare PyMySQL rows with opt-in ADBC Flight SQL result consumption."""
    from .infrastructure.analytical.benchmark import run_doris_flight_benchmark

    report = run_doris_flight_benchmark(
        store_manifest,
        output_dir,
        symbols=tuple(symbol),
        iterations=iterations,
        include_mysql=include_mysql,
        allow_unparameterized_fallback=allow_unparameterized_fallback,
        include_cold_connections=include_cold_connections,
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("check-doris-flight")
def check_doris_flight(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Optional external JSON path for the preflight evidence.",
    ),
    timeout_seconds: float = typer.Option(3.0, "--timeout-seconds", min=0.1, max=60.0),
) -> None:
    """Check the Flight overlay, startup logs, FE port, and advertised BE route."""
    from .infrastructure.analytical.benchmark import (
        run_doris_flight_preflight,
        write_doris_flight_preflight,
    )
    from .infrastructure.analytical.doris import DorisConfig

    report = run_doris_flight_preflight(
        DorisConfig.from_environment(), timeout_seconds=timeout_seconds
    )
    if output is not None:
        report["report_path"] = str(write_doris_flight_preflight(output, report))
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


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


def _runtime_for_selection(
    python_executable: Path | None, launcher: Path | None
) -> RuntimeDescriptor:
    if python_executable is not None and launcher is not None:
        raise typer.BadParameter("choose either --python-executable or --launcher")
    if python_executable is not None:
        try:
            ensure_project_importable(python_executable, Path.cwd())
            return probe_python_runtime(python_executable)
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
    if launcher is not None:
        return nuitka_runtime(launcher, current_runtime().python_version)
    return current_runtime()


def _runtime_comparisons(summaries: list[RunSummary]) -> list[dict[str, object]]:
    groups: dict[str, list[RunSummary]] = {}
    for summary in summaries:
        groups.setdefault(summary.runtime_name, []).append(summary)
    baseline_name = current_runtime().name
    baseline = groups.get(baseline_name, [])
    if not baseline:
        return []
    result: list[dict[str, object]] = []
    for runtime_name, candidates in sorted(groups.items()):
        if runtime_name == baseline_name:
            continue
        metrics: dict[str, object] = {}
        for name in ("wall_time_seconds", "peak_rss_bytes", "read_bytes", "write_bytes"):
            baseline_mean = _mean_metric(baseline, name)
            candidate_mean = _mean_metric(candidates, name)
            if baseline_mean is None or candidate_mean is None:
                continue
            metrics[name] = {
                "baseline_mean": baseline_mean,
                "candidate_mean": candidate_mean,
                "delta": candidate_mean - baseline_mean,
            }
        result.append(
            {
                "baseline": baseline_name,
                "candidate": runtime_name,
                "metrics": metrics,
            }
        )
    return result


def _mean_metric(summaries: list[RunSummary], name: str) -> float | None:
    values = [
        float(metric.value)
        for summary in summaries
        for metric in summary.metrics
        if summary.status is EvidenceStatus.OBSERVED
        and metric.name == name
        and isinstance(metric.value, (int, float))
    ]
    return sum(values) / len(values) if values else None


__all__ = ["app"]

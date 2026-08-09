"""Typer command for profiler-led analytical materializer probes."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .domain.models.performance import RunSummary
from .infrastructure.performance import get_performance_artifact_dir
from .infrastructure.performance.workloads import build_materializer_workload
from .performance_analytical_cli import profile_workload


def profile_materializer(
    elf: Path = typer.Argument(..., help="ELF file to materialize."),
    output_dir: Path = typer.Option(..., "--output-dir", help="External target-store parent."),
    max_cus: int | None = typer.Option(8, "--max-cus", min=1, help="Bounded diagnostic CU count."),
    max_open_writers: int = typer.Option(16, "--max-open-writers", min=1),
    parquet_layout: str = typer.Option("family", "--parquet-layout"),
    rotate_writers_every_cus: int = typer.Option(64, "--rotate-writers-every-cus", min=0),
    checkpoint_every_cus: int | None = typer.Option(None, "--checkpoint-every-cus", min=1),
    profiler: list[str] = typer.Option(
        [],
        "--profiler",
        help="Profiler: scalene, scalene-libraries, cprofile, pyinstrument, py-spy, or tracemalloc; repeat or use all.",
    ),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir"),
    history_db: Path | None = typer.Option(None, "--history-db"),
    timeout_seconds: float = typer.Option(1800.0, "--timeout-seconds", min=0.1),
    sample_interval: float = typer.Option(0.1, "--sample-interval", min=0.01),
    name: str = typer.Option("analytical-materializer", "--name"),
) -> None:
    """Run each requested profiler against an isolated bounded Parquet producer."""
    if not profiler:
        raise typer.BadParameter("provide at least one --profiler")
    raw_root = (artifact_dir or get_performance_artifact_dir()).resolve()
    summaries: list[RunSummary] = []
    for index, profiler_name in enumerate(profiler):
        workload = build_materializer_workload(
            repository_root=Path.cwd(),
            name=f"{name}-{profiler_name}-{index}",
            elf=elf,
            output_dir=output_dir / f"{profiler_name}-{index}",
            max_cus=max_cus,
            max_open_writers=max_open_writers,
            parquet_layout=parquet_layout,
            rotate_writers_every_cus=rotate_writers_every_cus,
            checkpoint_every_cus=checkpoint_every_cus,
            timeout_seconds=timeout_seconds,
        )
        summaries.extend(
            profile_workload(
                workload,
                raw_root,
                history_db,
                sample_interval,
                (profiler_name,),
            )
        )
    typer.echo(json.dumps([summary.to_dict() for summary in summaries], indent=2, sort_keys=True))


__all__ = ["profile_materializer"]

"""Typer command for separate llvm-mca performance evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .infrastructure.performance.llvm_mca import analyze_assembly

AssemblyArgument = Annotated[
    Path, typer.Argument(help="Post-compile assembly containing MCA markers.")
]
ToolOption = Annotated[Path, typer.Option("--tool", help="Matching orbis-llvm-mca executable.")]
OutputOption = Annotated[
    Path,
    typer.Option("--output-dir", help="External directory for llvm-mca output and manifest."),
]
JsonOption = Annotated[bool, typer.Option("--json/--text", help="Request JSON or text output.")]
ShowEncodingOption = Annotated[bool, typer.Option("--show-encoding")]
TimelineOption = Annotated[bool, typer.Option("--timeline")]
ResourcePressureOption = Annotated[bool, typer.Option("--resource-pressure")]
TimeoutOption = Annotated[float, typer.Option("--timeout-seconds", min=0.1)]


def analyze_assembly_command(
    assembly: AssemblyArgument,
    tool: ToolOption,
    output_dir: OutputOption,
    json_output: JsonOption = True,
    show_encoding: ShowEncodingOption = False,
    timeline: TimelineOption = False,
    resource_pressure: ResourcePressureOption = False,
    timeout_seconds: TimeoutOption = 300.0,
) -> None:
    """Analyze marked compiler assembly as separate performance-model evidence."""
    evidence = analyze_assembly(
        assembly,
        tool,
        output_dir,
        json_output=json_output,
        show_encoding=show_encoding,
        timeline=timeline,
        resource_pressure=resource_pressure,
        timeout_seconds=timeout_seconds,
    )
    typer.echo(json.dumps(evidence.to_dict(), indent=2, sort_keys=True))


__all__ = ["analyze_assembly_command"]

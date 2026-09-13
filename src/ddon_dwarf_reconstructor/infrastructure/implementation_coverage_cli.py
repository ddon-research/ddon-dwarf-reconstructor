"""Typer callback for the isolated implementation coverage audit."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .implementation_coverage_audit import audit_implementation_coverage


def audit_implementation_coverage_command(
    implementation_report: Path = typer.Option(
        ...,
        "--implementation-report",
        help="Existing source-bound implementation report; it is never modified.",
    ),
    ida_c_dump: Path = typer.Option(
        ...,
        "--ida-c-dump",
        help="Independent IDA C dump used only for post-generation comparison.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="External directory for the isolated audit artifact.",
    ),
    elf: Path | None = typer.Option(
        None,
        "--elf",
        help="Optional ELF whose hash is retained as audit provenance only.",
    ),
) -> None:
    """Cross-check report completeness against IDA without feeding production."""
    try:
        output_path = audit_implementation_coverage(
            implementation_report,
            ida_c_dump,
            output_dir,
            elf=elf,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        typer.echo(f"Implementation coverage audit failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        json.dumps(
            {
                "status": "observed",
                "authority": "cross-validation-only",
                "production_pipeline_uses_ida": False,
                "audit_path": str(output_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


__all__ = ["audit_implementation_coverage_command"]

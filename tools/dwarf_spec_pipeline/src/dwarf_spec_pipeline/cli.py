"""Typer command-line interface for the DWARF specification pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import typer

from .pipeline import PipelineError, build
from .source_manifest import SourceError, load_manifest, verify_source
from .validation import ArtifactValidationError, validate_output_directory

app = typer.Typer(
    name="dwarf-spec-pipeline",
    help="Build and validate deterministic DWARF specification artifacts.",
    no_args_is_help=True,
    add_completion=True,
)


def _default_schema() -> Path:
    return Path("tools/dwarf_spec_pipeline/schema/dwarf-specification.schema.json")


def _run(operation: Callable[[], None]) -> None:
    try:
        operation()
    except (ArtifactValidationError, PipelineError, SourceError, OSError, ValueError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=2) from error


@app.command("build")
def build_command(
    manifest: Path = typer.Option(
        Path("tools/dwarf_spec_pipeline/config/sources.json"),
        "--manifest",
        help="Locked source manifest.",
    ),
    output_dir: Path = typer.Option(
        Path("docs/knowledge-base/dwarf-specification/generated"),
        "--output-dir",
        help="Published artifact directory.",
    ),
    work_dir: Path = typer.Option(
        Path(".cache/dwarf_spec_pipeline"),
        "--work-dir",
        help="Working and source-cache directory.",
    ),
    schema: Path = typer.Option(_default_schema(), "--schema", help="JSON Schema path."),
    version: list[int] = typer.Option(
        [],
        "--version",
        min=2,
        max=4,
        help="DWARF version to build; repeat for multiple versions.",
    ),
    offline: bool = typer.Option(False, "--offline", help="Require verified local sources."),
) -> None:
    """Build canonical JSON and Markdown artifacts."""

    def operation() -> None:
        build(
            manifest,
            output_dir,
            work_dir,
            schema,
            versions=set(version) if version else None,
            offline=offline,
        )
        typer.echo(f"Built DWARF artifacts in {output_dir}")

    _run(operation)


@app.command("validate")
def validate(
    output_dir: Path = typer.Option(
        Path("docs/knowledge-base/dwarf-specification/generated"),
        "--output-dir",
        help="Published artifact directory.",
    ),
    schema: Path = typer.Option(_default_schema(), "--schema", help="JSON Schema path."),
) -> None:
    """Validate generated artifacts against the JSON Schema and manifest."""

    def operation() -> None:
        validate_output_directory(output_dir, schema)
        typer.echo(f"Validated DWARF artifacts in {output_dir}")

    _run(operation)


@app.command("sources")
def sources(
    manifest: Path = typer.Option(
        Path("tools/dwarf_spec_pipeline/config/sources.json"),
        "--manifest",
        help="Locked source manifest.",
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/dwarf_spec_pipeline/sources"),
        "--cache-dir",
        help="Verified source-cache directory.",
    ),
) -> None:
    """Verify cached source documents against the locked manifest."""

    def operation() -> None:
        source_manifest = load_manifest(manifest)
        for source in source_manifest.sources:
            path = cache_dir / source.source_id / source.filename
            verify_source(path, source)
        typer.echo(f"Verified {len(source_manifest.sources)} cached DWARF sources")

    _run(operation)


def main(argv: list[str] | None = None) -> int:
    """Invoke the Typer application from Python callers."""
    try:
        result = app(args=argv, prog_name="dwarf-spec-pipeline", standalone_mode=False)
    except typer.Exit as error:
        return error.exit_code or 0
    return result if isinstance(result, int) else 0


if __name__ == "__main__":  # pragma: no cover
    app()

"""Unified Typer command-line interface for the DDON DWARF reconstructor."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import typer

from .artifact_cli import app as artifacts_app
from .main import GenerationOptions, run_generation
from .performance_cli import app as performance_app

app = typer.Typer(
    name="ddon-dwarf-reconstructor",
    help="Reconstruct deterministic C++ headers and maintain DWARF artifacts.",
    no_args_is_help=True,
    add_completion=True,
)
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(performance_app, name="performance")


def _package_version() -> str:
    try:
        return version("ddon-dwarf-reconstructor")
    except PackageNotFoundError:
        return "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_package_version())
        raise typer.Exit()


@app.callback()
def _root(
    version_flag: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Run deterministic DWARF reconstruction and artifact maintenance commands."""
    del version_flag


def _options(
    *,
    elf_file: Path,
    symbols: list[str],
    symbols_file: Path | None,
    output: Path | None,
    verbose: bool,
    full_hierarchy: bool,
    single_file: bool,
    exhaustive: bool,
    dwarf_dump: Path | None,
    dwarf_index: Path | None,
    dwarf_store_manifest: Path | None = None,
    export_knowledge: Path | None = None,
    build_id: str | None = None,
    orbis_objdump: Path | None = None,
    resolve_param_names: bool = False,
    tool_export_manifests: tuple[Path, ...] = (),
) -> GenerationOptions:
    return GenerationOptions(
        elf_file=elf_file,
        symbols=tuple(symbols),
        symbols_file=symbols_file,
        output=output,
        verbose=verbose,
        full_hierarchy=full_hierarchy,
        single_file=single_file,
        exhaustive=exhaustive,
        dwarf_dump=dwarf_dump,
        dwarf_index=dwarf_index,
        dwarf_store_manifest=dwarf_store_manifest,
        export_knowledge=export_knowledge,
        build_id=build_id,
        orbis_objdump=orbis_objdump,
        resolve_param_names=resolve_param_names,
        tool_export_manifests=tool_export_manifests,
    )


def _run(options: GenerationOptions) -> None:
    exit_code = run_generation(options)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command()
def generate(
    elf_file: Path = typer.Argument(..., help="Path to the ELF file to analyze."),
    symbol: list[str] = typer.Option(
        [],
        "--symbol",
        "-s",
        help="Symbol to generate; repeat for multiple symbols.",
    ),
    symbols_file: Path | None = typer.Option(
        None,
        "--symbols-file",
        metavar="FILE",
        help="File containing one symbol per line.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: ./output).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs."),
    full_hierarchy: bool = typer.Option(
        False, "--full-hierarchy", help="Generate the full hierarchy."
    ),
    single_file: bool = typer.Option(
        False, "--single-file", help="Render the full hierarchy into one header."
    ),
    exhaustive: bool = typer.Option(
        False, "--exhaustive", help="Search all CUs for the best definition."
    ),
    dwarf_dump: Path | None = typer.Option(
        None,
        "--dwarf-dump",
        metavar="PATH",
        help="Validation-only compressed DWARF dump; rejected for normal generation.",
    ),
    dwarf_index: Path | None = typer.Option(
        None,
        "--dwarf-index",
        metavar="PATH",
        help="Validation-only DWARF SQLite sidecar; rejected for normal generation.",
    ),
    dwarf_store_manifest: Path | None = typer.Option(
        None,
        "--dwarf-store",
        metavar="MANIFEST",
        help="Complete source-bound manifest whose projection is already published in Doris.",
    ),
    resolve_param_names: bool = typer.Option(
        False,
        "--resolve-param-names",
        help="Search method implementations for parameter names.",
    ),
) -> None:
    """Generate deterministic C++ headers for one or more symbols."""
    _run(
        _options(
            elf_file=elf_file,
            symbols=symbol,
            symbols_file=symbols_file,
            output=output,
            verbose=verbose,
            full_hierarchy=full_hierarchy,
            single_file=single_file,
            exhaustive=exhaustive,
            dwarf_dump=dwarf_dump,
            dwarf_index=dwarf_index,
            dwarf_store_manifest=dwarf_store_manifest,
            resolve_param_names=resolve_param_names,
        )
    )


@app.command("export-knowledge")
def export_knowledge(
    elf_file: Path = typer.Argument(..., help="Path to the ELF file to analyze."),
    output_dir: Path = typer.Option(
        ..., "--output-dir", help="Directory in which to publish the knowledge bundle."
    ),
    symbol: list[str] = typer.Option(
        [], "--symbol", "-s", help="Symbol to export; repeat for multiple symbols."
    ),
    symbols_file: Path | None = typer.Option(
        None, "--symbols-file", metavar="FILE", help="File containing one symbol per line."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs."),
    exhaustive: bool = typer.Option(
        False, "--exhaustive", help="Search all CUs for the best definition."
    ),
    dwarf_dump: Path | None = typer.Option(
        None,
        "--dwarf-dump",
        metavar="PATH",
        help="Validation-only compressed DWARF dump; rejected for normal export.",
    ),
    dwarf_index: Path | None = typer.Option(
        None,
        "--dwarf-index",
        metavar="PATH",
        help="Validation-only DWARF SQLite sidecar; rejected for normal export.",
    ),
    dwarf_store_manifest: Path | None = typer.Option(
        None,
        "--dwarf-store",
        metavar="MANIFEST",
        help="Complete source-bound manifest whose projection is already published in Doris.",
    ),
    build_id: str | None = typer.Option(None, "--build-id", help="Stable build identifier."),
    orbis_objdump: Path | None = typer.Option(
        None, "--orbis-objdump", metavar="PATH", help="Pinned Orbis objdump executable."
    ),
    resolve_param_names: bool = typer.Option(
        False, "--resolve-param-names", help="Search method implementations for parameter names."
    ),
    tool_evidence: list[Path] = typer.Option(
        [],
        "--tool-evidence",
        metavar="MANIFEST",
        help="Source-bound external-tool manifest; repeat to attach multiple exports.",
    ),
) -> None:
    """Export deterministic evidence for one or more symbols as a knowledge bundle."""
    _run(
        _options(
            elf_file=elf_file,
            symbols=symbol,
            symbols_file=symbols_file,
            output=output_dir,
            verbose=verbose,
            full_hierarchy=False,
            single_file=False,
            exhaustive=exhaustive,
            dwarf_dump=dwarf_dump,
            dwarf_index=dwarf_index,
            dwarf_store_manifest=dwarf_store_manifest,
            export_knowledge=output_dir,
            build_id=build_id,
            orbis_objdump=orbis_objdump,
            resolve_param_names=resolve_param_names,
            tool_export_manifests=tuple(tool_evidence),
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Invoke the unified CLI from Python callers without argparse."""
    try:
        result = app(args=argv, prog_name="ddon-dwarf-reconstructor", standalone_mode=False)
    except typer.Exit as error:
        return error.exit_code or 0
    return result if isinstance(result, int) else 0


if __name__ == "__main__":  # pragma: no cover
    app()

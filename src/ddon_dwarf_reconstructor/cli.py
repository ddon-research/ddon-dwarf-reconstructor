"""Unified Typer command-line interface for the DDON DWARF reconstructor."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import typer

from .application.generation.options import DEFAULT_LLVM_TARGET_TRIPLE
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
    orbis_as: Path | None = None,
    llvm_readobj: Path | None = None,
    llvm_objdump: Path | None = None,
    llvm_target_triple: str = DEFAULT_LLVM_TARGET_TRIPLE,
    extract_assembly: bool = False,
    emit_implementation_sources: bool = False,
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
        orbis_as=orbis_as,
        llvm_readobj=llvm_readobj,
        llvm_objdump=llvm_objdump,
        llvm_target_triple=llvm_target_triple,
        extract_assembly=extract_assembly,
        emit_implementation_sources=emit_implementation_sources,
        resolve_param_names=resolve_param_names,
        tool_export_manifests=tool_export_manifests,
    )


def _run(options: GenerationOptions) -> None:
    exit_code = run_generation(options)
    if exit_code:
        raise typer.Exit(code=exit_code)


_GENERATE_SYMBOL_HELP = "Symbol to generate; repeat for multiple symbols."
_GENERATE_SYMBOLS_FILE_HELP = "File containing one symbol per line."
_GENERATE_OUTPUT_HELP = "Output directory (default: ./output)."
_GENERATE_DUMP_HELP = "Validation-only compressed DWARF dump; rejected for normal generation."
_GENERATE_INDEX_HELP = "Validation-only DWARF SQLite sidecar; rejected for normal generation."
_GENERATE_STORE_HELP = (
    "Complete source-bound manifest whose projection is already published in Doris."
)
_GENERATE_ASSEMBLY_HELP = (
    "Run additive implementation and Orbis assembly discovery after headers succeed."
)
_GENERATE_ORBIS_HELP = "Orbis objdump executable used by --extract-assembly when available."
_GENERATE_ORBIS_AS_HELP = (
    "Orbis assembler used to turn emitted canonical .s files into .o files; when omitted, "
    "a sibling orbis-as next to --orbis-objdump is used."
)
_GENERATE_LLVM_HELP = (
    "Optional llvm-readobj executable for additive generic-ELF JSON cross-check evidence."
)
_GENERATE_LLVM_OBJDUMP_HELP = (
    "Optional llvm-objdump executable for per-method additive LLVM disassembly cross-checks."
)
_GENERATE_LLVM_TRIPLE_HELP = "LLVM target triple for --llvm-objdump (default: x86_64-scei-ps4)."
_GENERATE_SOURCE_HELP = (
    "Emit canonical PS4 .s artifacts and, when orbis-as is available, .o objects for unique "
    "matches. C++ translation is a later workflow. Requires --extract-assembly."
)
_GENERATE_PARAMS_HELP = "Search method implementations for parameter names."
_EXPORT_OUTPUT_HELP = "Directory in which to publish the knowledge bundle."
_EXPORT_DUMP_HELP = "Validation-only compressed DWARF dump; rejected for normal export."
_EXPORT_INDEX_HELP = "Validation-only DWARF SQLite sidecar; rejected for normal export."
_EXPORT_STORE_HELP = (
    "Complete source-bound manifest whose projection is already published in Doris."
)
_EXPORT_TOOL_EVIDENCE_HELP = (
    "Source-bound external-tool manifest; repeat to attach multiple exports."
)


@app.command()
def generate(
    elf_file: Path = typer.Argument(..., help="Path to the ELF file to analyze."),
    symbol: list[str] = typer.Option([], "--symbol", "-s", help=_GENERATE_SYMBOL_HELP),
    symbols_file: Path | None = typer.Option(
        None, "--symbols-file", metavar="FILE", help=_GENERATE_SYMBOLS_FILE_HELP
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help=_GENERATE_OUTPUT_HELP),
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
        None, "--dwarf-dump", metavar="PATH", help=_GENERATE_DUMP_HELP
    ),
    dwarf_index: Path | None = typer.Option(
        None, "--dwarf-index", metavar="PATH", help=_GENERATE_INDEX_HELP
    ),
    dwarf_store_manifest: Path | None = typer.Option(
        None, "--dwarf-store", metavar="MANIFEST", help=_GENERATE_STORE_HELP
    ),
    extract_assembly: bool = typer.Option(
        False,
        "--extract-assembly",
        help=_GENERATE_ASSEMBLY_HELP,
    ),
    orbis_objdump: Path | None = typer.Option(
        None, "--orbis-objdump", metavar="PATH", help=_GENERATE_ORBIS_HELP
    ),
    orbis_as: Path | None = typer.Option(
        None, "--orbis-as", metavar="PATH", help=_GENERATE_ORBIS_AS_HELP
    ),
    llvm_readobj: Path | None = typer.Option(
        None, "--llvm-readobj", metavar="PATH", help=_GENERATE_LLVM_HELP
    ),
    llvm_objdump: Path | None = typer.Option(
        None, "--llvm-objdump", metavar="PATH", help=_GENERATE_LLVM_OBJDUMP_HELP
    ),
    llvm_target_triple: str = typer.Option(
        "x86_64-scei-ps4", "--llvm-target-triple", help=_GENERATE_LLVM_TRIPLE_HELP
    ),
    emit_implementation_sources: bool = typer.Option(
        False, "--emit-implementation-sources", help=_GENERATE_SOURCE_HELP
    ),
    resolve_param_names: bool = typer.Option(
        False, "--resolve-param-names", help=_GENERATE_PARAMS_HELP
    ),
) -> None:
    """Generate deterministic C++ headers for one or more symbols."""
    option_values = locals()
    option_values["symbols"] = option_values.pop("symbol")
    _run(_options(**option_values))


@app.command("export-knowledge")
def export_knowledge(
    elf_file: Path = typer.Argument(..., help="Path to the ELF file to analyze."),
    output_dir: Path = typer.Option(..., "--output-dir", help=_EXPORT_OUTPUT_HELP),
    symbol: list[str] = typer.Option([], "--symbol", "-s", help=_GENERATE_SYMBOL_HELP),
    symbols_file: Path | None = typer.Option(
        None, "--symbols-file", metavar="FILE", help=_GENERATE_SYMBOLS_FILE_HELP
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs."),
    exhaustive: bool = typer.Option(
        False, "--exhaustive", help="Search all CUs for the best definition."
    ),
    dwarf_dump: Path | None = typer.Option(
        None, "--dwarf-dump", metavar="PATH", help=_EXPORT_DUMP_HELP
    ),
    dwarf_index: Path | None = typer.Option(
        None, "--dwarf-index", metavar="PATH", help=_EXPORT_INDEX_HELP
    ),
    dwarf_store_manifest: Path | None = typer.Option(
        None, "--dwarf-store", metavar="MANIFEST", help=_EXPORT_STORE_HELP
    ),
    build_id: str | None = typer.Option(None, "--build-id", help="Stable build identifier."),
    orbis_objdump: Path | None = typer.Option(
        None, "--orbis-objdump", metavar="PATH", help="Pinned Orbis objdump executable."
    ),
    llvm_readobj: Path | None = typer.Option(
        None, "--llvm-readobj", metavar="PATH", help=_GENERATE_LLVM_HELP
    ),
    llvm_objdump: Path | None = typer.Option(
        None, "--llvm-objdump", metavar="PATH", help=_GENERATE_LLVM_OBJDUMP_HELP
    ),
    llvm_target_triple: str = typer.Option(
        "x86_64-scei-ps4", "--llvm-target-triple", help=_GENERATE_LLVM_TRIPLE_HELP
    ),
    resolve_param_names: bool = typer.Option(
        False, "--resolve-param-names", help=_GENERATE_PARAMS_HELP
    ),
    tool_evidence: list[Path] = typer.Option(
        [], "--tool-evidence", metavar="MANIFEST", help=_EXPORT_TOOL_EVIDENCE_HELP
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
            llvm_readobj=llvm_readobj,
            llvm_objdump=llvm_objdump,
            llvm_target_triple=llvm_target_triple,
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

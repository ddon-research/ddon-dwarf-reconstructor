"""Typer commands for durable reconstructor artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import typer

from .domain.models.analytical_dwarf import DwarfMaterializationRequest
from .domain.models.tool_evidence import TOOL_EXPORT_SCHEMA_VERSION
from .domain.repositories.cache import PersistentSymbolCache
from .infrastructure.analytical.doris import (
    DorisConfig,
    DorisLoader,
    build_doris_plan,
)
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.config import get_cache_file_path
from .infrastructure.elf_evidence import inspect_elf
from .infrastructure.logging import LoggerSetup, get_logger, log_exception
from .infrastructure.toolchain_exports import (
    ToolchainExporter,
    list_tool_export_profiles,
)
from .infrastructure.toolchain_exports import (
    probe_tool as probe_external_tool,
)
from .infrastructure.zstd_dump_evidence import inspect_dump
from .infrastructure.zstd_dump_parser import ZstdDumpParser

logger = get_logger(__name__)

app = typer.Typer(
    name="artifacts",
    help="Inspect and explicitly maintain durable local DWARF artifacts.",
    no_args_is_help=True,
)


def _inspect(
    elf_path: Path | None,
    dump_path: Path | None,
    dump_index: Path | None,
    *,
    include_catalog_sources: bool,
) -> dict[str, Any]:
    if elf_path is None and dump_path is None:
        raise ValueError("inspect requires --elf, --dwarf-dump, or both")
    result: dict[str, Any] = {
        "source_catalog": SourceIdentityCatalog().inspect(include_sources=include_catalog_sources)
    }
    if elf_path is not None:
        cache_path = get_cache_file_path(str(elf_path))
        if cache_path.exists():
            symbol_cache = PersistentSymbolCache(cache_path)
            result["symbol_cache"] = {
                "path": str(cache_path),
                "exists": True,
                "statistics": symbol_cache.get_statistics(),
                "source_fingerprint": symbol_cache.data.get("source_fingerprint"),
            }
        else:
            result["symbol_cache"] = {"path": str(cache_path), "exists": False}
    if dump_path is not None:
        result["dump_index"] = ZstdDumpParser(dump_path, dump_index).inspect_index()
    return result


def _write_result(result: dict[str, Any]) -> None:
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


def _run_operation(operation: Callable[[], None]) -> None:
    try:
        LoggerSetup.initialize(Path("logs"))
        operation()
    except Exception as error:
        log_exception(logger, "artifact_operation_failed", error, operation=operation.__name__)
        typer.echo(f"Artifact operation failed: {error}", err=True)
        raise typer.Exit(code=1) from error


@app.command("inspect")
def inspect(
    elf: Path | None = typer.Option(None, "--elf", help="ELF path for symbol-cache status."),
    dwarf_dump: Path | None = typer.Option(
        None, "--dwarf-dump", help="Compressed DWARF dump path."
    ),
    dump_index: Path | None = typer.Option(
        None, "--dump-index", help="Explicit DWARF SQLite sidecar."
    ),
    include_catalog_sources: bool = typer.Option(
        False, "--include-catalog-sources", help="Include catalog source records."
    ),
) -> None:
    """Read source-catalog, symbol-cache, and dump-index status as JSON."""
    _run_operation(
        lambda: _write_result(
            _inspect(
                elf,
                dwarf_dump,
                dump_index,
                include_catalog_sources=include_catalog_sources,
            )
        )
    )


@app.command("verify-source")
def verify_source(
    source: Path = typer.Argument(..., help="Source file to hash and verify."),
) -> None:
    """Force a complete SHA-256 source verification."""

    def operation() -> None:
        identity = SourceIdentityCatalog().identify(source, verify=True)
        _write_result(
            {
                "path": str(source.resolve()),
                "status": "verified",
                "identity": {
                    "sha256": identity.sha256,
                    "size": identity.size,
                    "mtime_ns": identity.mtime_ns,
                    "ctime_ns": identity.ctime_ns,
                    "device": identity.device,
                    "inode": identity.inode,
                },
            }
        )

    _run_operation(operation)


@app.command("inspect-elf")
def inspect_elf_command(
    elf: Path = typer.Argument(..., help="ELF path to inspect."),
) -> None:
    """Inspect ELF headers and all DWARF CU producer/version headers as JSON."""
    _run_operation(lambda: _write_result(inspect_elf(elf)))


@app.command("inspect-dwarf-dump")
def inspect_dwarf_dump(
    dwarf_dump: Path = typer.Argument(..., help="Compressed LLVM DWARF dump path."),
) -> None:
    """Stream a compressed LLVM dump and report CU versions and producers."""
    _run_operation(lambda: _write_result(inspect_dump(dwarf_dump)))


@app.command("materialize-dwarf")
def materialize_dwarf(
    elf: Path = typer.Argument(..., help="ELF path to materialize."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="External directory for the source-bound analytical store.",
    ),
    raw_chunk_size: int = typer.Option(
        8 * 1024 * 1024,
        "--raw-chunk-size",
        min=1,
        help="Bounded raw-section copy chunk size in bytes.",
    ),
    write_jsonl: bool = typer.Option(
        False,
        "--write-jsonl/--no-write-jsonl",
        help="Also publish the lossless JSONL audit/interchange projection.",
    ),
    write_parquet: bool = typer.Option(
        True,
        "--write-parquet/--no-write-parquet",
        help="Stream normalized rows directly to the Arrow/Parquet projection (default).",
    ),
    checkpoint_every_cus: int | None = typer.Option(
        None,
        "--checkpoint-every-cus",
        min=1,
        help="Publish an explicit in-progress Parquet snapshot after this many CUs.",
    ),
    max_cus: int | None = typer.Option(
        None,
        "--max-cus",
        min=1,
        help="Diagnostic only: stop after this many CUs and publish a partial store.",
    ),
    max_open_writers: int = typer.Option(
        16,
        "--max-open-writers",
        min=1,
        help="Maximum simultaneous native Parquet writers before rotating a part.",
    ),
    parquet_layout: str = typer.Option(
        "family",
        "--parquet-layout",
        help="Parquet layout: one family/source writer or bucketed directory writers.",
    ),
    rotate_writers_every_cus: int = typer.Option(
        64,
        "--rotate-writers-every-cus",
        min=0,
        help="Close Parquet family writers at this CU interval; 0 disables boundary rotation.",
    ),
) -> None:
    """Traverse CUs once and publish a source-bound lossless store."""
    request = DwarfMaterializationRequest(
        source_path=elf,
        output_dir=output_dir,
        raw_chunk_size=raw_chunk_size,
        write_jsonl=write_jsonl,
        write_parquet=write_parquet,
        checkpoint_every_cus=checkpoint_every_cus,
        max_cus=max_cus,
        max_open_writers=max_open_writers,
        parquet_layout=parquet_layout,
        rotate_writers_every_cus=rotate_writers_every_cus,
    )
    _run_operation(lambda: _run_materialization(request))


def _run_materialization(request: DwarfMaterializationRequest) -> None:
    from .infrastructure.analytical import DwarfMaterializer

    materializer = DwarfMaterializer()
    manifest = materializer.materialize(request)
    _write_result(
        {
            "manifest": manifest.to_dict(),
            "manifest_path": str(materializer.last_manifest_path),
            "last_checkpoint_manifest_path": (
                str(materializer.last_checkpoint_manifest_path)
                if materializer.last_checkpoint_manifest_path is not None
                else None
            ),
            "cu_passes": materializer.cu_passes,
        }
    )


@app.command("inspect-dwarf-store")
def inspect_dwarf_store(
    manifest: Path = typer.Argument(..., help="Analytical store manifest."),
    source_path: Path | None = typer.Option(
        None,
        "--source",
        help="Source ELF used to verify a manifest relocated from its recorded path.",
    ),
    verify_source: bool = typer.Option(
        True,
        "--verify-source/--no-verify-source",
        help="Verify the source identity before opening the store.",
    ),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help="Inspect an explicit checkpoint snapshot and report partial evidence.",
    ),
) -> None:
    """Validate and summarize a source-bound analytical store."""

    def operation() -> None:
        from .infrastructure.analytical import load_analytical_store

        store = load_analytical_store(
            manifest,
            verify_source=verify_source,
            source_path=source_path,
            allow_incomplete=allow_incomplete,
            verify_artifacts=True,
        )
        _write_result(
            {
                "manifest_path": str(store.manifest_path),
                "manifest": store.manifest.to_dict(),
                "unit_count": store.unit_count,
                "die_count": store.die_count,
                "definition_names": store.definition_name_count,
            }
        )

    _run_operation(operation)


@app.command("load-doris")
def load_doris(
    manifest: Path = typer.Argument(..., help="Analytical store manifest."),
    compose_file: Path | None = typer.Option(
        None,
        "--compose-file",
        help="Compose file recorded with the load evidence; it is not started implicitly.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only emit the validated SQL/file plan.",
    ),
    analyze: bool | None = typer.Option(
        None,
        "--analyze/--no-analyze",
        help="For native Doris, submit ANALYZE TABLE after loading; enabled by default.",
    ),
) -> None:
    """Load a complete source-bound analytical store into native Doris."""

    def operation() -> None:
        config = DorisConfig.from_environment()
        if analyze is not None:
            config = replace(config, analyze_after_load=analyze)
        plan = build_doris_plan(manifest, config)
        if dry_run:
            result: dict[str, Any] = {"status": "not_observed", "plan": plan.to_dict()}
        else:
            result = DorisLoader().execute(plan, config)
        if compose_file is not None:
            result["compose_file"] = str(compose_file.resolve())
        _write_result(result)

    _run_operation(operation)


@app.command("list-tool-profiles")
def list_tool_profiles() -> None:
    """List bounded external-tool export profiles and authority boundaries."""
    _run_operation(
        lambda: _write_result(
            {
                "profiles": [
                    {
                        "name": profile.name,
                        "tool_name": profile.tool_name,
                        "arguments": list(profile.arguments),
                        "output_format": profile.output_format,
                        "authority": profile.authority,
                        "max_output_bytes": profile.max_output_bytes,
                        "description": profile.description,
                    }
                    for profile in list_tool_export_profiles()
                ]
            }
        )
    )


@app.command("probe-tool")
def probe_tool(
    tool: Path = typer.Argument(..., help="External tool executable to probe."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory in which to publish version and bounded --help artifacts.",
    ),
    timeout_seconds: float = typer.Option(
        30.0,
        "--timeout-seconds",
        min=0.1,
        help="Maximum time for each tool probe command.",
    ),
) -> None:
    """Capture a source-independent tool identity and bounded help artifact."""

    def operation() -> None:
        result = probe_external_tool(tool, output_dir, timeout_seconds=timeout_seconds)
        tool_info = result.get("tool")
        if not isinstance(tool_info, dict) or not isinstance(tool_info.get("sha256"), str):
            raise ValueError("Tool probe returned no stable tool identity")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", tool.stem)
        result["probe_path"] = str(
            (
                output_dir
                / f"{safe_name}-v{TOOL_EXPORT_SCHEMA_VERSION}-{tool_info['sha256'][:16]}"
                / "probe.json"
            ).resolve()
        )
        _write_result(result)

    _run_operation(operation)


@app.command("export-tool-evidence")
def export_tool_evidence(
    source: Path = typer.Argument(..., help="ELF/DWARF source to inspect."),
    tool: Path = typer.Option(..., "--tool", help="External inspection tool executable."),
    profile: str = typer.Option(..., "--profile", help="Named bounded export profile."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory in which to publish the source-bound export bundle.",
    ),
    timeout_seconds: float = typer.Option(
        300.0,
        "--timeout-seconds",
        min=0.1,
        help="Maximum time for each external tool command.",
    ),
) -> None:
    """Run one explicit tool profile and publish its raw output plus manifest."""

    def operation() -> None:
        exporter = ToolchainExporter(timeout_seconds=timeout_seconds)
        result = exporter.export(source, tool, profile, output_dir)
        payload = result.to_dict()
        payload["manifest_path"] = str(
            (output_dir / result.artifact_key / result.manifest_name).resolve()
        )
        payload["cache_hit"] = exporter.last_cache_hit
        _write_result(payload)

    _run_operation(operation)


def _dump_operation(dwarf_dump: Path, index_path: Path | None, *, rebuild: bool) -> None:
    parser = ZstdDumpParser(dwarf_dump, index_path)
    _write_result(parser.rebuild_index() if rebuild else parser.repair_index())


@app.command("repair-dump-index")
def repair_dump_index(
    dwarf_dump: Path = typer.Argument(..., help="Compressed DWARF dump path."),
    index_path: Path | None = typer.Option(None, "--index-path", help="Explicit sidecar path."),
) -> None:
    """Repair metadata or build a missing dump index."""
    _run_operation(lambda: _dump_operation(dwarf_dump, index_path, rebuild=False))


@app.command("rebuild-dump-index")
def rebuild_dump_index(
    dwarf_dump: Path = typer.Argument(..., help="Compressed DWARF dump path."),
    index_path: Path | None = typer.Option(None, "--index-path", help="Explicit sidecar path."),
) -> None:
    """Force one complete streaming scan and atomically publish a dump index."""
    _run_operation(lambda: _dump_operation(dwarf_dump, index_path, rebuild=True))


@app.command("repair-catalog")
def repair_catalog() -> None:
    """Remove source-catalog paths that no longer exist."""
    _run_operation(
        lambda: _write_result(
            {
                "path": str(SourceIdentityCatalog().path),
                **SourceIdentityCatalog().prune_missing_paths(),
            }
        )
    )


@app.command("repair-symbol-cache")
def repair_symbol_cache(
    elf: Path = typer.Option(..., "--elf", help="ELF path whose cache is replaced."),
    from_cache: Path = typer.Option(..., "--from-cache", help="Replacement cache path."),
) -> None:
    """Restore a symbol cache from an explicit replacement file."""

    def operation() -> None:
        cache_path = get_cache_file_path(str(elf))
        cache = PersistentSymbolCache(cache_path)
        _write_result(
            {
                "path": str(cache_path),
                "restored_from": str(from_cache.resolve()),
                "statistics": cache.restore_from(from_cache),
            }
        )

    _run_operation(operation)


@app.command("purge-dump-index")
def purge_dump_index(
    dwarf_dump: Path = typer.Argument(..., help="Compressed DWARF dump path."),
    index_path: Path | None = typer.Option(None, "--index-path", help="Explicit sidecar path."),
    confirm_index_path: Path = typer.Option(
        ...,
        "--confirm-index-path",
        help="Exact resolved index path reported by inspect.",
    ),
) -> None:
    """Delete one named dump index after exact-path confirmation."""

    def operation() -> None:
        parser = ZstdDumpParser(dwarf_dump, index_path)
        expected = parser.index_path.resolve()
        confirmed = confirm_index_path.resolve()
        if confirmed != expected:
            raise ValueError(f"Confirmation path does not match index: {confirmed} != {expected}")
        existed = expected.exists()
        if existed:
            expected.unlink()
        _write_result({"kind": "compressed-dwarf-index", "path": str(expected), "purged": existed})

    _run_operation(operation)


def main(argv: list[str] | None = None) -> int:
    """Invoke the artifact sub-application from Python callers."""
    try:
        result = app(
            args=argv,
            prog_name="ddon-dwarf-reconstructor artifacts",
            standalone_mode=False,
        )
    except typer.Exit as error:
        return error.exit_code or 0
    return result if isinstance(result, int) else 0


if __name__ == "__main__":  # pragma: no cover
    app()

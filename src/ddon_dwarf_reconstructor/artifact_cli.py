"""Typer commands for durable reconstructor artifacts."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from .domain.repositories.cache import PersistentSymbolCache
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.config import get_cache_file_path
from .infrastructure.zstd_dump_parser import ZstdDumpParser

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
        operation()
    except (OSError, ValueError) as error:
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

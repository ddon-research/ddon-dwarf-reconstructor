"""Operator CLI for durable reconstructor artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .domain.repositories.cache import PersistentSymbolCache
from .infrastructure.artifacts import SourceIdentityCatalog
from .infrastructure.config import get_cache_file_path
from .infrastructure.zstd_dump_parser import ZstdDumpParser


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ddon-dwarf-artifacts",
        description="Inspect and explicitly maintain durable local DWARF artifacts.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Read artifact status")
    inspect_parser.add_argument("--elf", type=Path)
    inspect_parser.add_argument("--dwarf-dump", type=Path)
    inspect_parser.add_argument("--dump-index", type=Path)
    inspect_parser.add_argument("--include-catalog-sources", action="store_true")

    verify_parser = subparsers.add_parser(
        "verify-source", help="Force a complete SHA-256 verification"
    )
    verify_parser.add_argument("source", type=Path)

    for action in ("repair-dump-index", "rebuild-dump-index"):
        action_parser = subparsers.add_parser(action)
        action_parser.add_argument("dwarf_dump", type=Path)
        action_parser.add_argument("--index-path", type=Path)

    subparsers.add_parser("repair-catalog", help="Remove catalog paths that no longer exist")

    symbol_repair = subparsers.add_parser(
        "repair-symbol-cache", help="Restore a symbol cache from an explicit cache file"
    )
    symbol_repair.add_argument("--elf", type=Path, required=True)
    symbol_repair.add_argument("--from-cache", type=Path, required=True)

    purge_parser = subparsers.add_parser("purge-dump-index", help="Delete one named dump index")
    purge_parser.add_argument("dwarf_dump", type=Path)
    purge_parser.add_argument("--index-path", type=Path)
    purge_parser.add_argument(
        "--confirm-index-path",
        type=Path,
        required=True,
        help="Exact resolved index path reported by inspect",
    )
    return parser


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
    print(json.dumps(result, indent=2, sort_keys=True))


def _handle_inspect(args: argparse.Namespace) -> None:
    _write_result(
        _inspect(
            args.elf,
            args.dwarf_dump,
            args.dump_index,
            include_catalog_sources=args.include_catalog_sources,
        )
    )


def _handle_verify_source(args: argparse.Namespace) -> None:
    identity = SourceIdentityCatalog().identify(args.source, verify=True)
    _write_result(
        {
            "path": str(args.source.resolve()),
            "status": "verified",
            "identity": {
                "sha256": identity.sha256,
                "size": identity.size,
                "boundary_sha256": identity.boundary_sha256,
            },
        }
    )


def _handle_dump_action(args: argparse.Namespace) -> None:
    parser = ZstdDumpParser(args.dwarf_dump, args.index_path)
    action = args.action
    result = parser.repair_index() if action == "repair-dump-index" else parser.rebuild_index()
    _write_result(result)


def _handle_repair_catalog(_args: argparse.Namespace) -> None:
    catalog = SourceIdentityCatalog()
    _write_result({"path": str(catalog.path), **catalog.prune_missing_paths()})


def _handle_symbol_cache_repair(args: argparse.Namespace) -> None:
    cache_path = get_cache_file_path(str(args.elf))
    cache = PersistentSymbolCache(cache_path)
    _write_result(
        {
            "path": str(cache_path),
            "restored_from": str(args.from_cache.resolve()),
            "statistics": cache.restore_from(args.from_cache),
        }
    )


def _handle_dump_purge(args: argparse.Namespace) -> None:
    parser = ZstdDumpParser(args.dwarf_dump, args.index_path)
    expected = parser.index_path.resolve()
    confirmed = args.confirm_index_path.resolve()
    if confirmed != expected:
        raise ValueError(f"Confirmation path does not match index: {confirmed} != {expected}")
    existed = expected.exists()
    if existed:
        expected.unlink()
    _write_result({"kind": "compressed-dwarf-index", "path": str(expected), "purged": existed})


def main(argv: list[str] | None = None) -> int:
    """Run an explicit durable-artifact operation."""
    args = _parser().parse_args(argv)
    try:
        handlers: dict[str, Callable[[argparse.Namespace], None]] = {
            "inspect": _handle_inspect,
            "verify-source": _handle_verify_source,
            "repair-dump-index": _handle_dump_action,
            "rebuild-dump-index": _handle_dump_action,
            "repair-catalog": _handle_repair_catalog,
            "repair-symbol-cache": _handle_symbol_cache_repair,
            "purge-dump-index": _handle_dump_purge,
        }
        handler = handlers.get(args.action)
        if handler is None:  # pragma: no cover - argparse restricts choices
            raise ValueError(f"Unsupported action: {args.action}")
        handler(args)
    except (OSError, ValueError) as error:
        print(f"Artifact operation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Tests for explicit durable-artifact operations."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ddon_dwarf_reconstructor.artifact_cli import app
from ddon_dwarf_reconstructor.domain.repositories.cache import PersistentSymbolCache
from ddon_dwarf_reconstructor.infrastructure.config import get_cache_file_path


class StableCliRunner(CliRunner):
    """Keep Typer's isolated streams alive while pytest suspends capture for logs."""

    @contextmanager
    def isolation(
        self,
        input: str | bytes | None = None,
        env: Mapping[str, str | None] | None = None,
        color: bool = False,
    ) -> Iterator[tuple[io.BytesIO, io.BytesIO, io.BytesIO]]:
        with super().isolation(input=input, env=env, color=color) as streams:
            preserved_streams: tuple[Any, ...] = (sys.stdin, sys.stdout, sys.stderr)
            yield streams
            _ = preserved_streams


runner = StableCliRunner()


@pytest.mark.unit
def test_inspect_reports_missing_dump_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "cache"))
    dump_path = tmp_path / "dump.zst"
    dump_path.write_bytes(b"fixture")

    result = runner.invoke(app, ["inspect", "--dwarf-dump", str(dump_path)])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["dump_index"]["status"] == "missing"
    assert payload["dump_index"]["exists"] is False


@pytest.mark.unit
def test_purge_requires_exact_resolved_index_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "cache"))
    dump_path = tmp_path / "dump.zst"
    index_path = tmp_path / "dump.zst.index.sqlite3"
    dump_path.write_bytes(b"fixture")
    index_path.write_bytes(b"derived")

    result = runner.invoke(
        app,
        [
            "purge-dump-index",
            str(dump_path),
            "--confirm-index-path",
            str(tmp_path / "wrong.sqlite3"),
        ],
    )
    assert result.exit_code == 1
    assert index_path.exists()

    result = runner.invoke(
        app,
        [
            "purge-dump-index",
            str(dump_path),
            "--confirm-index-path",
            str(index_path),
        ],
    )
    assert result.exit_code == 0
    assert not index_path.exists()


@pytest.mark.unit
def test_symbol_cache_repair_replaces_instead_of_merging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "cache"))
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"elf")
    target_path = get_cache_file_path(str(elf_path))
    target = PersistentSymbolCache(target_path)
    target.add_symbol_cu_mapping("keep", 1, 2)
    target.add_symbol_cu_mapping("remove", 3, 4)
    target.save()
    replacement_path = tmp_path / "replacement.json"
    replacement = PersistentSymbolCache(replacement_path)
    replacement.add_symbol_cu_mapping("keep", 1, 2)
    replacement.save()

    result = runner.invoke(
        app,
        [
            "repair-symbol-cache",
            "--elf",
            str(elf_path),
            "--from-cache",
            str(replacement_path),
        ],
    )
    assert result.exit_code == 0

    restored = PersistentSymbolCache(target_path)
    assert restored.get_symbol_offset("keep") == 2
    assert restored.get_symbol_offset("remove") is None

"""Tests for explicit durable-artifact operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.artifact_cli import main
from ddon_dwarf_reconstructor.domain.repositories.cache import PersistentSymbolCache
from ddon_dwarf_reconstructor.infrastructure.config import get_cache_file_path


@pytest.mark.unit
def test_inspect_reports_missing_dump_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "cache"))
    dump_path = tmp_path / "dump.zst"
    dump_path.write_bytes(b"fixture")

    assert main(["inspect", "--dwarf-dump", str(dump_path)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["dump_index"]["status"] == "missing"
    assert result["dump_index"]["exists"] is False


@pytest.mark.unit
def test_purge_requires_exact_resolved_index_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "cache"))
    dump_path = tmp_path / "dump.zst"
    index_path = tmp_path / "dump.zst.index.sqlite3"
    dump_path.write_bytes(b"fixture")
    index_path.write_bytes(b"derived")

    assert (
        main(
            [
                "purge-dump-index",
                str(dump_path),
                "--confirm-index-path",
                str(tmp_path / "wrong.sqlite3"),
            ]
        )
        == 1
    )
    assert index_path.exists()
    capsys.readouterr()

    assert (
        main(
            [
                "purge-dump-index",
                str(dump_path),
                "--confirm-index-path",
                str(index_path),
            ]
        )
        == 0
    )
    assert not index_path.exists()


@pytest.mark.unit
def test_symbol_cache_repair_replaces_instead_of_merging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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

    assert (
        main(
            [
                "repair-symbol-cache",
                "--elf",
                str(elf_path),
                "--from-cache",
                str(replacement_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    restored = PersistentSymbolCache(target_path)
    assert restored.get_symbol_offset("keep") == 2
    assert restored.get_symbol_offset("remove") is None

"""Tests for durable immutable-source identities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import time

import pytest

import ddon_dwarf_reconstructor.infrastructure.artifacts as artifacts
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog


@pytest.mark.unit
def test_catalog_hashes_source_once_across_fresh_instances(tmp_path: Path, mocker) -> None:
    """A warm fresh process reuses the established strong source identity."""
    source = tmp_path / "DDOORBIS.elf"
    source.write_bytes(b"immutable-elf" * 20_000)
    catalog_path = tmp_path / "source-identities.json"

    first = SourceIdentityCatalog(catalog_path).identify(source)
    hash_spy = mocker.patch(
        "ddon_dwarf_reconstructor.infrastructure.artifacts.sha256_file",
        side_effect=AssertionError("warm identity rehashed the complete source"),
    )
    second = SourceIdentityCatalog(catalog_path).identify(source)

    assert second == first
    hash_spy.assert_not_called()


@pytest.mark.unit
def test_catalog_reuses_identity_after_source_relocation(tmp_path: Path, mocker) -> None:
    """The immutable-input lookup key does not depend on an absolute path."""
    original = tmp_path / "first" / "DDOORBIS.elf"
    relocated = tmp_path / "second" / "DDOORBIS.elf"
    original.parent.mkdir()
    relocated.parent.mkdir()
    original.write_bytes(b"relocatable-source" * 20_000)
    catalog_path = tmp_path / "source-identities.json"
    identity = SourceIdentityCatalog(catalog_path).identify(original)
    original.replace(relocated)

    hash_spy = mocker.patch(
        "ddon_dwarf_reconstructor.infrastructure.artifacts.sha256_file",
        side_effect=AssertionError("relocation rehashed the complete source"),
    )
    relocated_identity = SourceIdentityCatalog(catalog_path).identify(relocated)

    assert relocated_identity == identity
    hash_spy.assert_not_called()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    record = catalog["sources"][identity.lookup_key]
    assert str(original.resolve()) in record["paths"]
    assert str(relocated.resolve()) in record["paths"]


@pytest.mark.unit
def test_verify_forces_strong_hash_and_refreshes_catalog(tmp_path: Path, mocker) -> None:
    """Explicit verification never trusts only the immutable-input fast key."""
    source = tmp_path / "dump.zst"
    source.write_bytes(b"dump" * 40_000)
    catalog = SourceIdentityCatalog(tmp_path / "source-identities.json")
    expected = catalog.identify(source)
    hash_spy = mocker.spy(
        __import__("ddon_dwarf_reconstructor.infrastructure.artifacts", fromlist=["sha256_file"]),
        "sha256_file",
    )

    verified = catalog.identify(source, verify=True)

    assert verified == expected
    hash_spy.assert_called_once_with(source.resolve())


@pytest.mark.unit
def test_catalog_publication_is_valid_json(tmp_path: Path) -> None:
    """Published catalogs are complete deterministic JSON documents."""
    source = tmp_path / "source.bin"
    source.write_bytes(b"source")
    catalog_path = tmp_path / "catalog.json"

    SourceIdentityCatalog(catalog_path).identify(source)

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert len(data["sources"]) == 1


@pytest.mark.unit
def test_catalog_rejects_same_path_source_replacement(tmp_path: Path) -> None:
    """Replacing content at one path creates a new durable source identity."""
    source = tmp_path / "DDOORBIS.elf"
    source.write_bytes(b"source-v1" * 20_000)
    catalog = SourceIdentityCatalog(tmp_path / "source-identities.json")

    first = catalog.identify(source)
    source.write_bytes(b"source-v2" * 20_000)
    second = catalog.identify(source)

    assert second != first
    assert second.sha256 != first.sha256


@pytest.mark.unit
def test_catalog_rehashes_same_size_middle_replacement(tmp_path: Path) -> None:
    """A replacement outside the sampled regions receives a new strong identity."""
    source = tmp_path / "DDOORBIS.elf"
    source.write_bytes(b"a" * 200_000)
    catalog = SourceIdentityCatalog(tmp_path / "source-identities.json")
    first = catalog.identify(source)

    replacement = bytearray(b"a" * 200_000)
    replacement[100_000:100_010] = b"changed!!!"
    source.write_bytes(replacement)
    os.utime(source, ns=(first.mtime_ns + 1_000_000, first.mtime_ns + 1_000_000))

    second = catalog.identify(source)

    assert second.size == first.size
    assert second.sha256 != first.sha256


@pytest.mark.unit
def test_catalog_rejects_non_object_root_document(tmp_path: Path) -> None:
    """Malformed catalog roots are treated as empty catalogs."""
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("[]", encoding="utf-8")

    assert SourceIdentityCatalog(catalog_path).inspect()["source_count"] == 0


@pytest.mark.unit
def test_cache_directory_selection_honors_all_supported_environment_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DWARF_CACHE_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert artifacts.get_artifact_cache_dir() == tmp_path / "xdg" / "ddon-dwarf-reconstructor"

    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert artifacts.get_artifact_cache_dir() == tmp_path / "local" / "ddon-dwarf-reconstructor"

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(artifacts.Path, "home", staticmethod(lambda: tmp_path / "home"))
    assert (
        artifacts.get_artifact_cache_dir()
        == tmp_path / "home" / ".cache" / "ddon-dwarf-reconstructor"
    )


@pytest.mark.unit
def test_catalog_inspection_pruning_and_record_validation(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source" * 20_000)
    catalog_path = tmp_path / "catalog.json"
    catalog = SourceIdentityCatalog(catalog_path)
    identity = catalog.identify(source)

    inspected = catalog.inspect(include_sources=True)
    assert inspected["source_count"] == 1
    assert "sources" in inspected

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    record = payload["sources"][identity.lookup_key]
    record["paths"].append(str(tmp_path / "missing.bin"))
    payload["sources"]["dead-record"] = {"paths": [str(tmp_path / "gone.bin")]}
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    assert catalog.prune_missing_paths() == {"paths_removed": 2, "records_removed": 1}
    catalog.record(source, identity)
    with pytest.raises(ValueError, match="no longer matches"):
        catalog.record(source, artifacts.SourceIdentity("0" * 64, 1, 0, 0, 0, 0))


@pytest.mark.unit
def test_catalog_load_recovers_from_invalid_and_wrong_schema_documents(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("not-json", encoding="utf-8")
    catalog = SourceIdentityCatalog(catalog_path)
    assert catalog.inspect()["source_count"] == 0

    catalog_path.write_text(json.dumps({"schema_version": "old", "sources": []}), encoding="utf-8")
    assert catalog.inspect()["source_count"] == 0


@pytest.mark.unit
def test_catalog_lock_reclaims_stale_lock_and_times_out_active_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = SourceIdentityCatalog(tmp_path / "catalog.json")
    lock_path = catalog.path.with_suffix(f"{catalog.path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("stale", encoding="utf-8")
    old = time() - 10
    os.utime(lock_path, (old, old))
    monkeypatch.setattr(artifacts, "STALE_LOCK_SECONDS", 0.0)
    with catalog._exclusive_lock():
        assert lock_path.exists()
    assert not lock_path.exists()

    lock_path.write_text("active", encoding="utf-8")
    monkeypatch.setattr(artifacts, "STALE_LOCK_SECONDS", 10_000.0)
    monkeypatch.setattr(artifacts, "LOCK_TIMEOUT_SECONDS", 0.0)
    try:
        with pytest.raises(TimeoutError, match="Timed out"), catalog._exclusive_lock():
            pass
    finally:
        lock_path.unlink(missing_ok=True)

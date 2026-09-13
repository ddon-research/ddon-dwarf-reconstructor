"""Repeated relocation reuse without weakening source mutation detection."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure import artifacts

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@dataclass(frozen=True)
class RelocatedSource:
    source: Path
    catalog_path: Path
    identity: artifacts.SourceIdentity
    metadata: artifacts.SourceMetadata


@pytest.fixture
def relocated_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RelocatedSource:
    original = tmp_path / "original.elf"
    source = tmp_path / "relocated.elf"
    original.write_bytes(b"immutable-source")
    catalog_path = tmp_path / "catalog.json"
    identity = artifacts.SourceIdentityCatalog(catalog_path).identify(original)
    metadata = replace(artifacts.probe_source(original), ctime_ns=identity.ctime_ns + 1)
    original.replace(source)
    monkeypatch.setattr(artifacts, "probe_source", lambda _path: metadata)
    assert artifacts.SourceIdentityCatalog(catalog_path).identify(source) == identity
    return RelocatedSource(source, catalog_path, identity, metadata)


def test_relocation_acceptance_survives_record_and_pruning(
    relocated_source: RelocatedSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = relocated_source
    hash_source = Mock(side_effect=AssertionError("warm source was rehashed"))
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)
    catalog = artifacts.SourceIdentityCatalog(state.catalog_path)

    catalog.record(state.source, state.identity)
    assert catalog.prune_missing_paths() == {"paths_removed": 1, "records_removed": 0}
    assert (
        artifacts.SourceIdentityCatalog(state.catalog_path).identify(state.source) == state.identity
    )
    hash_source.assert_not_called()


@pytest.mark.parametrize("ctime_delta", [0, 2])
def test_later_ctime_change_rehashes_even_when_original_ctime_returns(
    relocated_source: RelocatedSource,
    monkeypatch: pytest.MonkeyPatch,
    ctime_delta: int,
) -> None:
    state = relocated_source
    metadata = replace(state.metadata, ctime_ns=state.identity.ctime_ns + ctime_delta)
    monkeypatch.setattr(artifacts, "probe_source", lambda _path: metadata)
    hash_source = Mock(wraps=artifacts.sha256_file)
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    refreshed = artifacts.SourceIdentityCatalog(state.catalog_path).identify(state.source)

    hash_source.assert_called_once_with(state.source.resolve())
    assert refreshed.sha256 == state.identity.sha256
    assert refreshed.ctime_ns == metadata.ctime_ns


def test_verify_rehashes_a_relocated_source(
    relocated_source: RelocatedSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = relocated_source
    hash_source = Mock(wraps=artifacts.sha256_file)
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    verified = artifacts.SourceIdentityCatalog(state.catalog_path).identify(
        state.source, verify=True
    )

    hash_source.assert_called_once_with(state.source.resolve())
    assert verified.sha256 == state.identity.sha256
    assert verified.ctime_ns == state.metadata.ctime_ns


@pytest.mark.parametrize("observed_ctime", [None, True, "invalid", [], {}])
def test_malformed_observed_ctime_cannot_authorize_reuse(
    relocated_source: RelocatedSource,
    monkeypatch: pytest.MonkeyPatch,
    observed_ctime: object,
) -> None:
    state = relocated_source
    catalog = json.loads(state.catalog_path.read_text(encoding="utf-8"))
    catalog["sources"][state.identity.lookup_key]["observed_ctime_ns"] = observed_ctime
    state.catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    hash_source = Mock(wraps=artifacts.sha256_file)
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    refreshed = artifacts.SourceIdentityCatalog(state.catalog_path).identify(state.source)

    hash_source.assert_called_once_with(state.source.resolve())
    assert refreshed.sha256 == state.identity.sha256


def test_second_relocation_preserves_identity_and_warm_reuse(
    relocated_source: RelocatedSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = relocated_source
    destination = state.source.with_name("third-location.elf")
    state.source.replace(destination)
    metadata = replace(state.metadata, ctime_ns=state.metadata.ctime_ns + 1)
    monkeypatch.setattr(artifacts, "probe_source", lambda _path: metadata)
    hash_source = Mock(side_effect=AssertionError("second relocation rehashed source"))
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    for _attempt in range(2):
        assert (
            artifacts.SourceIdentityCatalog(state.catalog_path).identify(destination)
            == state.identity
        )
    hash_source.assert_not_called()


def test_new_path_with_existing_original_does_not_authorize_ctime_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tmp_path / "original.elf"
    other = tmp_path / "other.elf"
    original.write_bytes(b"same-source")
    other.write_bytes(b"same-source")
    catalog = artifacts.SourceIdentityCatalog(tmp_path / "catalog.json")
    identity = catalog.identify(original)
    metadata = replace(artifacts.probe_source(original), ctime_ns=identity.ctime_ns + 1)
    monkeypatch.setattr(artifacts, "probe_source", lambda _path: metadata)
    hash_source = Mock(wraps=artifacts.sha256_file)
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    catalog.identify(other)

    hash_source.assert_called_once_with(other.resolve())


def test_legacy_record_without_observed_ctime_reuses_matching_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "original.elf"
    source.write_bytes(b"immutable-source")
    catalog_path = tmp_path / "catalog.json"
    identity = artifacts.SourceIdentityCatalog(catalog_path).identify(source)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["sources"][identity.lookup_key].pop("observed_ctime_ns")
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    hash_source = Mock(side_effect=AssertionError("legacy metadata rehashed source"))
    monkeypatch.setattr(artifacts, "sha256_file", hash_source)

    assert artifacts.SourceIdentityCatalog(catalog_path).identify(source) == identity
    hash_source.assert_not_called()

"""Failures must release new resources and preserve recoverable publications."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure import artifact_io, symbol_output
from ddon_dwarf_reconstructor.infrastructure.analytical import session as session_module

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_failed_fsync_removes_new_temporary_file_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "retained.txt"
    target.write_bytes(b"previous\n")
    unrelated = tmp_path / ".unrelated.tmp"
    unrelated.write_bytes(b"retain")
    failure = OSError("fsync failed")
    monkeypatch.setattr(artifact_io.os, "fsync", Mock(side_effect=failure))

    with pytest.raises(OSError) as raised:
        artifact_io.atomic_write_text(target, "replacement\n")

    assert raised.value is failure
    assert target.read_bytes() == b"previous\n"
    assert set(tmp_path.iterdir()) == {target, unrelated}


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_failed_directory_commit_preserves_previous_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rollback_fails: bool
) -> None:
    stage, target = tmp_path / "stage", tmp_path / "target"
    stage.mkdir()
    target.mkdir()
    (stage / "new.h").write_bytes(b"new")
    (target / "old.h").write_bytes(b"old")
    replace = symbol_output.os.replace
    publication_error = PermissionError("publish denied")
    rollback_error = PermissionError("rollback denied")

    def fail_replace(source: Path, destination: Path) -> None:
        if source == stage:
            raise publication_error
        if source != target and rollback_fails:
            raise rollback_error
        replace(source, destination)

    monkeypatch.setattr(symbol_output.os, "replace", fail_replace)
    with pytest.raises(PermissionError) as raised:
        symbol_output._commit_directory(stage, target)

    if rollback_fails:
        assert raised.value is rollback_error
        assert raised.value.__context__ is publication_error
        backups = list(tmp_path.glob(".target.backup-*"))
        assert len(backups) == 1
        assert (backups[0] / "old.h").read_bytes() == b"old"
    else:
        assert raised.value is publication_error
        assert (target / "old.h").read_bytes() == b"old"
        assert not list(tmp_path.glob(".target.backup-*"))


@pytest.mark.parametrize("failure_stage", ["identity", "index", "view"])
def test_failed_session_entry_closes_acquired_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    store = Mock()
    store.manifest.source_identity.sha256 = "expected"
    identity = Mock(sha256="different" if failure_stage == "identity" else "expected")
    monkeypatch.setattr(
        session_module.SourceIdentityCatalog, "identify", Mock(return_value=identity)
    )
    monkeypatch.setattr(session_module.DorisDwarfStore, "load", Mock(return_value=store))
    if failure_stage == "index":
        monkeypatch.setattr(
            session_module, "DorisDwarfIndex", Mock(side_effect=RuntimeError("index"))
        )
    if failure_stage == "view":
        store.as_dwarf_info.side_effect = RuntimeError("view")
    session = session_module.AnalyticalDwarfSession(
        tmp_path / "manifest.json", expected_source_path=tmp_path / "source.elf"
    )

    with pytest.raises((ValueError, RuntimeError)):
        session.__enter__()

    store.close.assert_called_once_with()
    assert session.store is None
    assert session.query_port is None
    assert session.query_index is None
    assert session.dwarf_info is None
    session.close()
    store.close.assert_called_once_with()


def test_close_failure_still_releases_session_references(tmp_path: Path) -> None:
    session = session_module.AnalyticalDwarfSession(tmp_path / "manifest.json")
    store = Mock()
    store.close.side_effect = OSError("close failed")
    session.store = store
    session.query_port = store

    with pytest.raises(OSError, match="close failed"):
        session.close()

    assert session.store is None
    assert session.query_port is None
    session.close()
    store.close.assert_called_once_with()

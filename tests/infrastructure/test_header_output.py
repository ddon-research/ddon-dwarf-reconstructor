"""Failure recovery for publication over an existing header bundle."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core.platform import ELFPlatform
from ddon_dwarf_reconstructor.infrastructure import header_output

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


def test_invalid_header_name_preserves_existing_bundle(tmp_path: Path) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "original"})
    previous = _snapshot(directory)

    with pytest.raises(ValueError, match="single relative name"):
        publisher.publish(tmp_path, ELFPlatform.PS4, {"../escape.h": "replacement"})

    assert _snapshot(directory) == previous
    assert not tuple(directory.glob(".headers-*"))


@pytest.mark.parametrize("generate_context", [True, False])
@pytest.mark.parametrize("failure_type", [OSError, KeyboardInterrupt])
def test_interrupted_replacement_restores_previous_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    generate_context: bool,
    failure_type: type[BaseException],
) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(
        tmp_path, ELFPlatform.PS4, {"A.h": "original", "C.h": "retained"}
    )
    previous = _snapshot(directory)
    replace_file = header_output.os.replace
    failure = failure_type("publication interrupted")

    def fail_replacement(source: Path, destination: Path) -> None:
        if source.name == "B.h":
            raise failure
        replace_file(source, destination)

    monkeypatch.setattr(header_output.os, "replace", fail_replacement)

    with pytest.raises(failure_type) as raised:
        publisher.publish(
            tmp_path,
            ELFPlatform.PS4,
            {"A.h": "replacement", "B.h": "new"},
            generate_context=generate_context,
        )

    assert raised.value is failure
    assert _snapshot(directory) == previous
    assert not tuple(directory.glob(".headers-*"))


def test_manifest_replacement_failure_restores_deleted_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(
        tmp_path, ELFPlatform.PS4, {"A.h": "original", "C.h": "retained"}
    )
    previous = _snapshot(directory)
    replace_file = header_output.os.replace

    def fail_manifest(source: Path, destination: Path) -> None:
        if source.name == publisher.MANIFEST_NAME and not source.parent.name.startswith(
            ".headers-backup-"
        ):
            raise OSError("manifest publication interrupted")
        replace_file(source, destination)

    monkeypatch.setattr(header_output.os, "replace", fail_manifest)

    with pytest.raises(OSError, match="manifest publication interrupted"):
        publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "replacement"})

    assert _snapshot(directory) == previous
    assert not tuple(directory.glob(".headers-*"))


def test_failed_rollback_preserves_backups_and_original_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "original"})
    previous = _snapshot(directory)
    replace_file = header_output.os.replace
    publication_error = OSError("publication failed")
    rollback_error = OSError("recovery failed")

    def fail_publication_and_rollback(source: Path, destination: Path) -> None:
        if source.parent.name.startswith(".headers-backup-"):
            raise rollback_error
        if source.name == "B.h":
            raise publication_error
        replace_file(source, destination)

    monkeypatch.setattr(header_output.os, "replace", fail_publication_and_rollback)

    with pytest.raises(OSError, match="recovery failed") as raised:
        publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "replacement", "B.h": "new"})

    backups = tuple(directory.glob(".headers-backup-*"))
    assert len(backups) == 1
    assert _snapshot(backups[0]) == previous
    assert raised.value.__cause__ is publication_error
    assert str(backups[0]) in "\n".join(raised.value.__notes__)
    assert tuple(directory.glob(".headers-*")) == backups


def test_invalid_previous_manifest_is_not_deleted(tmp_path: Path) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "original"})
    (directory / publisher.MANIFEST_NAME).write_text("invalid-json", encoding="utf-8")
    previous = _snapshot(directory)

    with pytest.raises(ValueError, match="Cannot read existing header manifest"):
        publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "replacement"})

    assert _snapshot(directory) == previous
    assert not tuple(directory.glob(".headers-*"))


@pytest.mark.parametrize("filename", ["A.h", header_output.AtomicHeaderPublisher.MANIFEST_NAME])
def test_backup_failure_preserves_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    publisher = header_output.AtomicHeaderPublisher()
    directory, _ = publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "original"})
    previous = _snapshot(directory)
    copy_file = header_output.shutil.copy2

    def fail_backup(source: Path, destination: Path) -> Path:
        if source.name == filename:
            raise OSError("backup unavailable")
        return Path(copy_file(source, destination))

    monkeypatch.setattr(header_output.shutil, "copy2", fail_backup)

    with pytest.raises(OSError, match="backup unavailable"):
        publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "replacement"})

    assert _snapshot(directory) == previous
    assert not tuple(directory.glob(".headers-*"))

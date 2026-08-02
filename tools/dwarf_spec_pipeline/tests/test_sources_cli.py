from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dwarf_spec_pipeline import converters
from dwarf_spec_pipeline.cli import main
from dwarf_spec_pipeline.source_manifest import (
    SourceError,
    SourceSpec,
    acquire_source,
    load_manifest,
    verify_source,
)


def _source_for_bytes(content: bytes) -> SourceSpec:
    return SourceSpec(
        source_id="dwarf2",
        standard_version=2,
        title="DWARF Version 2",
        filename="dwarf.v2.mm",
        format="mm",
        url="https://example.invalid/dwarf.v2.mm",
        source_page="https://example.invalid/doc/",
        sha256=hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.unit
def test_offline_acquisition_verifies_checksum_and_rejects_corruption(tmp_path: Path) -> None:
    content = b"locked source"
    source = _source_for_bytes(content)
    cached = tmp_path / "cache" / source.source_id / source.filename
    cached.parent.mkdir(parents=True)
    cached.write_bytes(content)

    assert acquire_source(source, tmp_path / "cache", offline=True) == cached
    cached.write_bytes(b"corrupt")
    with pytest.raises(SourceError, match="Checksum mismatch"):
        verify_source(cached, source)
    with pytest.raises(SourceError, match="Offline mode"):
        acquire_source(source, tmp_path / "other-cache", offline=True)


@pytest.mark.unit
def test_missing_converter_is_reported(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(converters.shutil, "which", lambda _name: None)
    source = _source_for_bytes(b"source")

    with pytest.raises(converters.ConversionError, match="groff"):
        converters.convert_source(source, tmp_path / source.filename, tmp_path / "work")


@pytest.mark.unit
def test_cli_reports_missing_sources_and_missing_artifacts(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    content = b"locked source"
    source = _source_for_bytes(content)
    manifest = tmp_path / "sources.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "sources": [source.model_dump(mode="json")]}) + "\n",
        encoding="utf-8",
    )

    assert (
        main(["sources", "--manifest", str(manifest), "--cache-dir", str(tmp_path / "cache")]) == 2
    )
    assert "Offline mode" not in capsys.readouterr().err
    assert (
        main(
            [
                "validate",
                "--output-dir",
                str(tmp_path / "missing-output"),
                "--schema",
                str(Path(__file__).parent.parent / "schema" / "dwarf-specification.schema.json"),
            ]
        )
        == 2
    )


@pytest.mark.unit
def test_malformed_source_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "malformed.json"
    manifest.write_text('{"sources": [', encoding="utf-8")

    with pytest.raises(SourceError, match="Unable to read source manifest"):
        load_manifest(manifest)

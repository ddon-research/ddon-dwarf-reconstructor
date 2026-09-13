from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dwarf_spec_pipeline import cli, converters, source_manifest
from dwarf_spec_pipeline.cli import app
from dwarf_spec_pipeline.source_manifest import (
    SourceError,
    SourceSpec,
    acquire_source,
    load_manifest,
    verify_source,
)

runner = CliRunner()


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
def test_cli_reports_missing_sources_and_missing_artifacts(tmp_path: Path) -> None:
    content = b"locked source"
    source = _source_for_bytes(content)
    manifest = tmp_path / "sources.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "sources": [source.model_dump(mode="json")]}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["sources", "--manifest", str(manifest), "--cache-dir", str(tmp_path / "cache")],
    )
    assert result.exit_code == 2
    assert "Offline mode" not in result.stdout

    result = runner.invoke(
        app,
        [
            "validate",
            "--output-dir",
            str(tmp_path / "missing-output"),
            "--schema",
            str(Path(__file__).parent.parent / "schema" / "dwarf-specification.schema.json"),
        ],
    )
    assert result.exit_code == 2


@pytest.mark.unit
def test_malformed_source_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "malformed.json"
    manifest.write_text('{"sources": [', encoding="utf-8")

    with pytest.raises(SourceError, match="Unable to read source manifest"):
        load_manifest(manifest)


@pytest.mark.unit
def test_failed_download_removes_only_new_temporary_file(monkeypatch, tmp_path: Path) -> None:
    content = b"locked source"
    source = _source_for_bytes(content)

    class FailingResponse:
        def __enter__(self) -> FailingResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _size: int) -> bytes:
            raise OSError("connection dropped")

    monkeypatch.setattr(source_manifest, "urlopen", lambda *_args, **_kwargs: FailingResponse())
    cache = tmp_path / "cache"
    with pytest.raises(SourceError, match="Unable to download"):
        acquire_source(source, cache)
    assert not list((cache / source.source_id).glob(".*"))


@pytest.mark.unit
def test_converter_runner_bounds_diagnostics_and_timeout(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('x' * 20000); raise SystemExit(3)",
    ]
    with pytest.raises(converters.ConversionError, match="truncated") as error:
        converters._run(command, cwd=tmp_path)
    assert len(str(error.value)) < 10_000

    timeout_command = [sys.executable, "-c", "import time; time.sleep(2)"]
    with pytest.raises(converters.ConversionError, match="timed out"):
        converters._run(timeout_command, cwd=tmp_path, timeout=0.01)


@pytest.mark.unit
def test_converter_publishes_staged_output_only_after_success(monkeypatch, tmp_path: Path) -> None:
    source = _source_for_bytes(b"source")
    source_path = tmp_path / source.filename
    source_path.write_bytes(b"source")
    output_dir = tmp_path / "work" / source.source_id
    output_dir.mkdir(parents=True)
    output_path = output_dir / f"{source.source_id}.html"
    output_path.write_text("old", encoding="utf-8")

    def succeed(*_args: object, output_path: Path | None = None, **_kwargs: object) -> None:
        assert output_path is not None
        output_path.write_text("new", encoding="utf-8")

    monkeypatch.setattr(converters, "_tool_path", lambda _name: sys.executable)
    monkeypatch.setattr(converters, "_run", succeed)
    assert converters.convert_source(source, source_path, tmp_path / "work") == output_path
    assert output_path.read_text(encoding="utf-8") == "new"

    def fail(*_args: object, **_kwargs: object) -> None:
        raise converters.ConversionError("converter failed")

    output_path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(converters, "_run", fail)
    with pytest.raises(converters.ConversionError, match="converter failed"):
        converters.convert_source(source, source_path, tmp_path / "work")
    assert output_path.read_text(encoding="utf-8") == "old"


@pytest.mark.unit
def test_cli_reports_converter_failure_with_specific_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            converters.ConversionError("converter failed")
        ),
    )
    result = runner.invoke(cli.app, ["build", "--manifest", str(tmp_path / "sources.json")])
    assert result.exit_code == 2
    assert "converter failed" in result.output

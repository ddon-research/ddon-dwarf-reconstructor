from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from dwarf_spec_pipeline import pipeline
from dwarf_spec_pipeline.pipeline import build
from dwarf_spec_pipeline.readers import RawBlock
from dwarf_spec_pipeline.source_manifest import SourceManifest
from dwarf_spec_pipeline.validation import load_and_validate_document


@pytest.mark.integration
@pytest.mark.functional
@pytest.mark.regression
def test_build_is_byte_deterministic_for_locked_intermediates(
    tmp_path: Path, source, schema_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "sources.json"
    manifest_path.write_text(
        SourceManifest(schema_version=1, sources=[source]).model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    intermediate = tmp_path / "intermediate.html"
    intermediate.write_text("<html />", encoding="utf-8")
    raw_blocks = [
        RawBlock(kind="heading", text="1. Introduction", level=1, index=0),
        RawBlock(kind="paragraph", text="Stable content.", index=1),
    ]
    monkeypatch.setattr(
        pipeline,
        "acquire_source",
        lambda _source, _cache_dir, *, offline: tmp_path / "source.mm",
    )
    monkeypatch.setattr(
        pipeline,
        "convert_source",
        lambda _source, _source_path, _work_dir: intermediate,
    )
    monkeypatch.setattr(
        pipeline,
        "read_intermediate",
        lambda _path, _intermediate: raw_blocks,
    )

    output_a = tmp_path / "generated-a"
    output_b = tmp_path / "generated-b"
    build(manifest_path, output_a, tmp_path / "work-a", schema_path)
    build(manifest_path, output_b, tmp_path / "work-b", schema_path)

    files_a = sorted(path.name for path in output_a.iterdir())
    files_b = sorted(path.name for path in output_b.iterdir())
    assert files_a == files_b == ["dwarf2.json", "dwarf2.md", "manifest.json"]
    assert [
        path.read_bytes() for path in sorted(output_a.iterdir(), key=lambda path: path.name)
    ] == [path.read_bytes() for path in sorted(output_b.iterdir(), key=lambda path: path.name)]
    load_and_validate_document(output_a / "dwarf2.json", schema_path)


@pytest.mark.unit
def test_publication_failure_restores_previous_directory(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "generated"
    output.mkdir()
    (output / "sentinel.txt").write_text("old", encoding="utf-8")
    stage = Path(tempfile.mkdtemp(prefix="stage-", dir=tmp_path))
    (stage / "sentinel.txt").write_text("new", encoding="utf-8")
    real_replace = pipeline.os.replace

    def fail_stage_swap(source: str | Path, destination: str | Path) -> None:
        if Path(source) == stage:
            raise OSError("simulated publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(pipeline.os, "replace", fail_stage_swap)
    try:
        with pytest.raises(OSError, match="simulated publication failure"):
            pipeline._publish(stage, output)
        assert (output / "sentinel.txt").read_text(encoding="utf-8") == "old"
        assert not any(
            path.name.startswith(f".{output.name}.backup-") for path in tmp_path.iterdir()
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)

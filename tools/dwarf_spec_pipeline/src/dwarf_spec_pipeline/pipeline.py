"""Orchestration for source acquisition, conversion, rendering, and publication."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .converters import convert_source
from .models import SpecificationDocument
from .normalize import build_document
from .readers import read_intermediate
from .rendering import render_json, render_markdown
from .source_manifest import SourceManifest, acquire_source, load_manifest
from .validation import validate_document


class PipelineError(RuntimeError):
    """Raised when a build cannot be completed."""


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _publish(stage: Path, output_dir: Path) -> None:
    """Swap a complete staged artifact directory into place.

    Renaming the previous directory out of the way first keeps readers from
    observing a half-published set of JSON/Markdown files. If the second
    rename fails, the previous publication is restored.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_dir.parent))
    backup.rmdir()
    os.replace(output_dir, backup)
    try:
        os.replace(stage, output_dir)
    except OSError:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        if backup.exists():
            os.replace(backup, output_dir)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def _artifact_manifest(
    manifest: SourceManifest, documents: list[tuple[SpecificationDocument, str, str]]
) -> str:
    artifacts = []
    for document, json_text, markdown_text in documents:
        artifacts.extend(
            [
                {
                    "path": f"dwarf{document.specification.version}.json",
                    "sha256": _sha256_bytes(json_text.encode("utf-8")),
                },
                {
                    "path": f"dwarf{document.specification.version}.md",
                    "sha256": _sha256_bytes(markdown_text.encode("utf-8")),
                },
            ]
        )
    payload = {
        "schema_version": 1,
        "parser_version": documents[0][0].parser_version if documents else "0.1.0",
        "sources": [source.model_dump(mode="json") for source in manifest.sources],
        "artifacts": sorted(artifacts, key=lambda item: item["path"]),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build(
    manifest_path: Path,
    output_dir: Path,
    work_dir: Path,
    schema_path: Path,
    *,
    versions: set[int] | None = None,
    offline: bool = False,
) -> None:
    manifest = load_manifest(manifest_path)
    selected = [
        source
        for source in sorted(manifest.sources, key=lambda item: item.standard_version)
        if versions is None or source.standard_version in versions
    ]
    if not selected:
        raise PipelineError("No requested DWARF versions are present in the source manifest")
    work_dir.mkdir(parents=True, exist_ok=True)
    source_cache = work_dir / "sources"
    intermediate_dir = work_dir / "intermediates"
    documents: list[tuple[SpecificationDocument, str, str]] = []

    for source in selected:
        source_path = acquire_source(source, source_cache, offline=offline)
        intermediate = convert_source(source, source_path, intermediate_dir)
        raw_blocks = read_intermediate(intermediate, "html" if source.format == "mm" else "docx")
        document = build_document(source, raw_blocks)
        validate_document(document, schema_path)
        documents.append((document, render_json(document), render_markdown(document)))

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".dwarf-spec-stage-", dir=output_dir.parent
    ) as stage_name:
        stage = Path(stage_name)
        for document, json_text, markdown_text in documents:
            version = document.specification.version
            (stage / f"dwarf{version}.json").write_text(json_text, encoding="utf-8", newline="\n")
            (stage / f"dwarf{version}.md").write_text(markdown_text, encoding="utf-8", newline="\n")
        selected_manifest = SourceManifest(schema_version=manifest.schema_version, sources=selected)
        (stage / "manifest.json").write_text(
            _artifact_manifest(selected_manifest, documents), encoding="utf-8", newline="\n"
        )
        _publish(stage, output_dir)

"""Schema and artifact validation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, cast

from jsonschema import ValidationError as JsonSchemaError
from jsonschema import validate as validate_json

from .models import SpecificationDocument
from .rendering import render_json
from .semantic import SemanticIndex
from .source_manifest import SourceManifest


class ArtifactValidationError(ValueError):
    """Raised when a generated artifact violates its contract."""


def load_schema(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ArtifactValidationError(f"Schema root must be an object: {path}")
        return cast(dict[str, Any], data)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Unable to read schema {path}: {exc}") from exc


def validate_document(document: SpecificationDocument, schema_path: Path) -> None:
    data = json.loads(render_json(document))
    try:
        validate_json(instance=data, schema=load_schema(schema_path))
    except JsonSchemaError as exc:
        raise ArtifactValidationError(
            f"Generated document failed JSON Schema validation: {exc}"
        ) from exc


def load_and_validate_document(path: Path, schema_path: Path) -> SpecificationDocument:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        document = SpecificationDocument.model_validate(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactValidationError(f"Invalid JSON artifact {path}: {exc}") from exc
    validate_document(document, schema_path)
    return document


def validate_output_directory(output_dir: Path, schema_path: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Invalid artifact manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list):
        raise ArtifactValidationError(f"Artifact manifest has an invalid shape: {manifest_path}")
    if manifest.get("schema_version") != 1:
        raise ArtifactValidationError(f"Unsupported artifact manifest schema: {manifest_path}")
    try:
        source_manifest = SourceManifest.model_validate(
            {"schema_version": manifest.get("schema_version"), "sources": manifest.get("sources")}
        )
    except ValueError as exc:
        raise ArtifactValidationError(
            f"Artifact manifest has invalid source identity: {exc}"
        ) from exc
    parser_version = manifest.get("parser_version")
    if not isinstance(parser_version, str) or not parser_version:
        raise ArtifactValidationError(
            f"Artifact manifest has invalid parser identity: {manifest_path}"
        )

    expected_hashes = _manifest_hashes(manifest["artifacts"], manifest_path)
    expected_paths = set(expected_hashes)
    actual_paths = _published_files(output_dir)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    if missing or extra:
        raise ArtifactValidationError(
            f"Artifact inventory mismatch: missing={missing}, extra={extra}"
        )
    for relative_path, expected in expected_hashes.items():
        artifact_path = output_dir / relative_path
        actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if expected != actual:
            raise ArtifactValidationError(
                f"Artifact checksum mismatch for {artifact_path}: expected {expected}, got {actual}"
            )

    versions = _document_versions(expected_paths, manifest_path)
    source_by_version = {source.standard_version: source for source in source_manifest.sources}
    if set(source_by_version) != versions:
        raise ArtifactValidationError(
            f"Manifest source/version identity mismatch: sources={sorted(source_by_version)}, "
            f"documents={sorted(versions)}"
        )
    for version in sorted(versions):
        json_path = output_dir / f"dwarf{version}.json"
        document = load_and_validate_document(json_path, schema_path)
        if document.parser_version != parser_version:
            raise ArtifactValidationError(f"Parser identity mismatch in {json_path}")
        source = source_by_version[version]
        if document.source.source_id != source.source_id or document.source.sha256 != source.sha256:
            raise ArtifactValidationError(f"Source identity mismatch in {json_path}")

    semantic_json = output_dir / "semantic-index.json"
    semantic_paths = {"semantic-index.json", "semantic-index.md"} & expected_paths
    if semantic_paths != {"semantic-index.json", "semantic-index.md"}:
        raise ArtifactValidationError("Semantic index requires both JSON and Markdown files")
    try:
        SemanticIndex.model_validate(json.loads(semantic_json.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactValidationError(f"Invalid semantic index: {exc}") from exc


_DOCUMENT_PATH_RE = re.compile(r"^dwarf([234])\.(json|md)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _manifest_hashes(artifacts: list[Any], manifest_path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ArtifactValidationError(f"Invalid artifact entry in {manifest_path}")
        relative_path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(relative_path, str) or not _valid_artifact_path(relative_path):
            raise ArtifactValidationError(f"Invalid artifact path {relative_path!r}")
        if relative_path == "manifest.json":
            raise ArtifactValidationError("The artifact manifest cannot contain itself")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ArtifactValidationError(f"Invalid artifact hash for {relative_path}")
        if relative_path in hashes:
            raise ArtifactValidationError(f"Duplicate artifact path {relative_path}")
        if not (
            _DOCUMENT_PATH_RE.fullmatch(relative_path)
            or relative_path.startswith("semantic-index.")
        ):
            raise ArtifactValidationError(f"Unknown artifact path {relative_path}")
        if relative_path.startswith("semantic-index.") and relative_path not in {
            "semantic-index.json",
            "semantic-index.md",
        }:
            raise ArtifactValidationError(f"Unknown artifact path {relative_path}")
        hashes[relative_path] = digest
    return hashes


def _valid_artifact_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        value == path.as_posix()
        and not path.is_absolute()
        and bool(path.parts)
        and all(part not in {".", ".."} for part in path.parts)
        and "\\" not in value
    )


def _published_files(output_dir: Path) -> set[str]:
    files: set[str] = set()
    for path in output_dir.rglob("*"):
        if path.is_symlink():
            raise ArtifactValidationError(f"Symlink is not a published artifact: {path}")
        if path.is_file():
            relative = path.relative_to(output_dir).as_posix()
            if relative != "manifest.json":
                files.add(relative)
    return files


def _document_versions(paths: set[str], manifest_path: Path) -> set[int]:
    json_versions = {
        int(match.group(1))
        for path in paths
        if (match := _DOCUMENT_PATH_RE.fullmatch(path)) and match.group(2) == "json"
    }
    markdown_versions = {
        int(match.group(1))
        for path in paths
        if (match := _DOCUMENT_PATH_RE.fullmatch(path)) and match.group(2) == "md"
    }
    if not json_versions or json_versions != markdown_versions:
        raise ArtifactValidationError(f"Document artifact pairs are incomplete: {manifest_path}")
    return json_versions

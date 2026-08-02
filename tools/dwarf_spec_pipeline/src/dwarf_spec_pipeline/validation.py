"""Schema and artifact validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import ValidationError as JsonSchemaError
from jsonschema import validate as validate_json

from .models import SpecificationDocument
from .rendering import render_json


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
    expected_hashes = {
        item.get("path"): item.get("sha256")
        for item in manifest["artifacts"]
        if isinstance(item, dict)
    }
    for version in (2, 3, 4):
        json_path = output_dir / f"dwarf{version}.json"
        markdown_path = output_dir / f"dwarf{version}.md"
        if not json_path.exists() or not markdown_path.exists():
            raise ArtifactValidationError(
                f"Missing artifact pair for DWARF {version} in {output_dir}"
            )
        load_and_validate_document(json_path, schema_path)
        for artifact_path in (json_path, markdown_path):
            relative_path = artifact_path.name
            expected = expected_hashes.get(relative_path)
            actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if expected != actual:
                raise ArtifactValidationError(
                    f"Artifact checksum mismatch for {artifact_path}: "
                    f"expected {expected}, got {actual}"
                )

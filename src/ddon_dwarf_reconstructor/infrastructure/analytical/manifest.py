"""Manifest loading and path-safety validation for analytical stores."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import (
    ANALYTICAL_SCHEMA_VERSION,
    DwarfRecordKind,
    MaterializationArtifact,
    MaterializationManifest,
)
from .dwarf_recovery import required_recovery_profile
from .optional import import_optional

_PARQUET_FILE_GLOB = "part-*.parquet"
_PARQUET_FAMILIES = frozenset(
    kind.value for kind in DwarfRecordKind if kind is not DwarfRecordKind.MANIFEST
)


def load_manifest(path: Path) -> MaterializationManifest:
    """Load a manifest without accepting malformed or partial JSON."""
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest root must be an object: {path}")
    return MaterializationManifest.from_dict(payload)


def has_parser_diagnostics(manifest: MaterializationManifest) -> bool:
    """Return whether structured DWARF emission recorded an incomplete CU."""
    status = manifest.configuration.get("dwarf_parse_status")
    count = manifest.configuration.get("parse_error_count")
    return status == "partial" or (
        isinstance(count, int) and not isinstance(count, bool) and count > 0
    )


def validate_schema_version(
    manifest: MaterializationManifest,
    *,
    allow_incomplete: bool,
) -> None:
    """Reject complete stores published before the current row schema."""
    if (
        not allow_incomplete
        and manifest.status == "complete"
        and manifest.schema_version != ANALYTICAL_SCHEMA_VERSION
    ):
        raise ValueError(
            "Analytical store schema is stale: "
            f"{manifest.schema_version!r}; expected {ANALYTICAL_SCHEMA_VERSION!r}"
        )


def has_unapplied_source_recovery(manifest: MaterializationManifest) -> bool:
    """Return whether a known source lacks its required evidence-backed repair profile."""
    required = required_recovery_profile(manifest.source_identity.sha256)
    if required is None:
        return False
    recovery = manifest.configuration.get("dwarf_recovery")
    return not (
        isinstance(recovery, dict)
        and recovery.get("status") in {"applied", "already_applied"}
        and recovery.get("profile") == required
    )


def validate_manifest_files(
    path: Path,
    manifest: MaterializationManifest,
    *,
    verify_hashes: bool = False,
    verify_payload: bool = False,
) -> None:
    """Validate paths, closed Parquet files, hashes, and optional payload reads."""
    root = path.resolve().parent
    for key, relative in manifest.files.items():
        candidate = (root / relative).resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"Manifest file escapes store root: {key}")
        if key not in {"raw_sections", "raw_values"} and not candidate.exists():
            raise FileNotFoundError(candidate)
        if key in {"raw_sections", "raw_values"} and not candidate.is_dir():
            raise NotADirectoryError(candidate)
    _validate_configured_paths(root, manifest.configuration.get("parquet_files"))
    _validate_artifacts(
        root,
        manifest,
        verify_hashes=verify_hashes,
        verify_payload=verify_payload or verify_hashes,
    )


def configured_parquet_files(
    manifest_path: Path, manifest: MaterializationManifest
) -> tuple[Path, ...] | None:
    """Return an optional immutable file list recorded by a checkpoint."""
    values = manifest.configuration.get("parquet_files")
    if values is None:
        return None
    root = manifest_path.resolve().parent
    return _configured_paths(root, values)


def declared_parquet_files(
    manifest_path: Path, manifest: MaterializationManifest
) -> tuple[Path, ...]:
    """Resolve the manifest-owned Parquet files and reject drift in complete stores."""
    root = manifest_path.resolve().parent
    parquet_root = _parquet_root(root, manifest)
    paths = _declared_paths(root, manifest_path, manifest)
    _validate_declared_parquet_paths(parquet_root, paths)
    _validate_complete_parquet_set(parquet_root, manifest, paths)
    return tuple(sorted(paths))


def validate_parquet_payloads(paths: Iterable[Path], *, parquet: Any | None = None) -> None:
    """Read every Parquet row group so publication proves compressed payload integrity."""
    reader_module = parquet or import_optional("pyarrow.parquet", "analytical")
    for path in paths:
        reader = reader_module.ParquetFile(path)
        _validate_parquet_payload(path, reader.metadata, reader_module, str(path))


def _validate_configured_paths(root: Path, values: object) -> None:
    if values is None:
        return
    for candidate in _configured_paths(root, values):
        if not candidate.is_file():
            raise FileNotFoundError(candidate)


def _validate_artifacts(
    root: Path,
    manifest: MaterializationManifest,
    *,
    verify_hashes: bool,
    verify_payload: bool,
) -> None:
    if "parquet" in manifest.files and not manifest.artifacts:
        raise ValueError("Parquet manifest has no closed artifact metadata")
    if not manifest.artifacts:
        return
    declared = {
        _validate_artifact(
            root,
            artifact,
            verify_hashes=verify_hashes,
            verify_payload=verify_payload,
        )
        for artifact in manifest.artifacts
    }
    configured = manifest.configuration.get("parquet_files")
    if configured is not None and set(_configured_paths(root, configured)) != declared:
        raise ValueError("Checkpoint Parquet file list does not match artifact metadata")
    if manifest.status == "complete":
        _validate_complete_parquet(root, manifest, declared)


def _validate_artifact(
    root: Path,
    artifact: MaterializationArtifact,
    *,
    verify_hashes: bool,
    verify_payload: bool,
) -> Path:
    candidate = _resolve_artifact(root, artifact)
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    stat = candidate.stat()
    if stat.st_size != artifact.size_bytes:
        raise ValueError(f"Artifact size changed: {artifact.path}")
    if artifact.modified_ns is not None and stat.st_mtime_ns != artifact.modified_ns:
        raise ValueError(f"Artifact modification time changed: {artifact.path}")
    if artifact.format == "parquet":
        _validate_parquet_footer(
            candidate,
            artifact,
            verify_hashes=verify_hashes,
            verify_payload=verify_payload,
        )
    if verify_hashes and _sha256_file(candidate) != artifact.sha256:
        raise ValueError(f"Artifact hash changed: {artifact.path}")
    return candidate


def _configured_paths(root: Path, values: object) -> tuple[Path, ...]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError("Manifest parquet_files must be a list of relative paths")
    paths = tuple((root / value).resolve() for value in values)
    if len(paths) != len(set(paths)):
        raise ValueError("Manifest has duplicate configured Parquet file paths")
    for path in paths:
        if root != path and root not in path.parents:
            raise ValueError(f"Manifest configured file escapes store root: {path}")
    return paths


def _parquet_root(root: Path, manifest: MaterializationManifest) -> Path:
    parquet_relative = manifest.files.get("parquet")
    if not isinstance(parquet_relative, str):
        raise ValueError("Analytical manifest does not declare a Parquet directory")
    parquet_root = (root / parquet_relative).resolve()
    if root != parquet_root and root not in parquet_root.parents:
        raise ValueError("Manifest Parquet directory escapes store root")
    if not parquet_root.is_dir():
        raise FileNotFoundError(parquet_root)
    return parquet_root


def _declared_paths(
    root: Path, manifest_path: Path, manifest: MaterializationManifest
) -> tuple[Path, ...]:
    configured = configured_parquet_files(manifest_path, manifest)
    if configured is not None:
        return configured
    paths = tuple(
        _resolve_artifact(root, artifact)
        for artifact in manifest.artifacts
        if artifact.format == "parquet"
    )
    if len(paths) != len(set(paths)):
        raise ValueError("Manifest has duplicate Parquet artifact paths")
    return paths


def _validate_complete_parquet_set(
    parquet_root: Path,
    manifest: MaterializationManifest,
    paths: tuple[Path, ...],
) -> None:
    if manifest.status != "complete":
        return
    actual = {
        candidate.resolve()
        for candidate in parquet_root.rglob(_PARQUET_FILE_GLOB)
        if candidate.is_file()
    }
    if actual != set(paths):
        raise ValueError("Complete Parquet store does not match its artifact manifest")


def _validate_declared_parquet_paths(parquet_root: Path, paths: tuple[Path, ...]) -> None:
    if not paths:
        raise FileNotFoundError(f"No Parquet files declared under {parquet_root}")
    for path in paths:
        if parquet_root != path and parquet_root not in path.parents:
            raise ValueError(f"Manifest Parquet file escapes its projection: {path}")
        if not path.match(_PARQUET_FILE_GLOB):
            raise ValueError(f"Manifest Parquet file has an invalid name: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        relative = path.relative_to(parquet_root)
        if not relative.parts or relative.parts[0] not in _PARQUET_FAMILIES:
            raise ValueError(f"Manifest Parquet file has an unsupported family: {path}")


def _validate_complete_parquet(
    root: Path,
    manifest: MaterializationManifest,
    declared: set[Path],
) -> None:
    parquet_relative = manifest.files.get("parquet")
    if parquet_relative is None:
        return
    parquet_root = (root / parquet_relative).resolve()
    actual = {
        candidate.resolve()
        for candidate in parquet_root.rglob(_PARQUET_FILE_GLOB)
        if candidate.is_file()
    }
    if actual != declared:
        raise ValueError("Complete Parquet store does not match its artifact manifest")
    _validate_projection_manifest(parquet_root)


def _resolve_artifact(root: Path, artifact: MaterializationArtifact) -> Path:
    candidate = (root / artifact.path).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"Manifest artifact escapes store root: {artifact.path}")
    return candidate


def _validate_projection_manifest(parquet_root: Path) -> None:
    path = parquet_root / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or payload.get("status") != "complete":
        raise ValueError(f"Parquet projection is not complete: {path}")


def _validate_parquet_footer(
    path: Path,
    artifact: MaterializationArtifact,
    *,
    verify_hashes: bool,
    verify_payload: bool,
) -> None:
    _validate_closed_footer(path, artifact.path)
    if not verify_hashes and not verify_payload:
        return
    parquet = import_optional("pyarrow.parquet", "analytical")
    metadata = parquet.ParquetFile(path).metadata
    _validate_parquet_metadata(artifact, metadata)
    if verify_payload:
        _validate_parquet_payload(path, metadata, parquet, artifact.path)


def _validate_closed_footer(path: Path, relative_path: str) -> None:
    if path.stat().st_size < 8:
        raise ValueError(f"Parquet artifact is too small to be closed: {relative_path}")
    with path.open("rb") as stream:
        if stream.read(4) != b"PAR1":
            raise ValueError(f"Parquet artifact has no header footer: {relative_path}")
        stream.seek(-4, 2)
        if stream.read(4) != b"PAR1":
            raise ValueError(f"Parquet artifact has no closed footer: {relative_path}")


def _validate_parquet_metadata(artifact: MaterializationArtifact, metadata: Any) -> None:
    rows = tuple(
        int(metadata.row_group(index).num_rows) for index in range(metadata.num_row_groups)
    )
    if artifact.row_group_count != int(metadata.num_row_groups):
        raise ValueError(f"Parquet row-group count changed: {artifact.path}")
    if artifact.row_group_rows != rows:
        raise ValueError(f"Parquet row-group metadata changed: {artifact.path}")
    if artifact.compression != _compression(metadata):
        raise ValueError(f"Parquet compression metadata changed: {artifact.path}")


def _validate_parquet_payload(path: Path, metadata: Any, parquet: Any, relative_path: str) -> None:
    reader = parquet.ParquetFile(path)
    for row_group in range(int(metadata.num_row_groups)):
        try:
            reader.read_row_group(row_group)
        except Exception as error:
            raise ValueError(
                f"Parquet payload is unreadable: {relative_path} row group {row_group}"
            ) from error


def _compression(metadata: Any) -> str | None:
    values = {
        str(metadata.row_group(index).column(column).compression).lower()
        for index in range(metadata.num_row_groups)
        for column in range(metadata.row_group(index).num_columns)
    }
    if not values:
        return None
    return next(iter(values)) if len(values) == 1 else "mixed"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialization_manifest_path(output_dir: Path, source_sha256: str) -> Path:
    """Return the deterministic manifest location for a source identity."""
    return output_dir / f"store-{source_sha256[:16]}" / "manifest.json"

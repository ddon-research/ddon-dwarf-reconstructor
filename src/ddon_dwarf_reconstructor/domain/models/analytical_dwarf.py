"""Typed contracts for source-bound analytical DWARF records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..ports.source_identity import SourceIdentity

type JsonPrimitive = None | bool | int | float | str
type TaggedJson = JsonPrimitive | dict[str, Any] | list[Any]

ANALYTICAL_SCHEMA_VERSION = "1.1"


class DwarfRecordKind(StrEnum):
    """Canonical analytical row families shared by all projections."""

    MANIFEST = "manifest"
    SECTION = "section"
    RAW_CHUNK = "raw_chunk"
    UNIT = "unit"
    DIE = "die"
    ATTRIBUTE = "attribute"
    REFERENCE = "reference"
    INDEX = "index"
    RANGE = "range"
    LOCATION = "location"
    LINE = "line"
    MACRO = "macro"
    FRAME = "frame"
    ABBREVIATION = "abbreviation"
    NAME = "name"


class QueryStatus(StrEnum):
    """Evidence states returned by an analytical store query."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


PARQUET_LAYOUTS = frozenset({"family", "bucketed"})


@dataclass(frozen=True, slots=True)
class DwarfMaterializationRequest:
    """Immutable input to one source-bound materialization run."""

    source_path: Path
    output_dir: Path
    schema_version: str = ANALYTICAL_SCHEMA_VERSION
    raw_chunk_size: int = 8 * 1024 * 1024
    write_jsonl: bool = False
    write_parquet: bool = True
    checkpoint_every_cus: int | None = None
    max_cus: int | None = None
    max_open_writers: int = 16
    parquet_layout: str = "family"
    rotate_writers_every_cus: int = 64

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        if self.raw_chunk_size <= 0:
            raise ValueError("raw_chunk_size must be positive")
        if self.max_open_writers <= 0:
            raise ValueError("max_open_writers must be positive")
        if self.rotate_writers_every_cus < 0:
            raise ValueError("rotate_writers_every_cus must be non-negative")
        if self.parquet_layout not in PARQUET_LAYOUTS:
            raise ValueError(f"parquet_layout must be one of {sorted(PARQUET_LAYOUTS)}")
        if not self.write_jsonl and not self.write_parquet:
            raise ValueError("at least one analytical projection must be enabled")
        _validate_checkpoint_request(
            self.checkpoint_every_cus,
            has_parquet=self.write_parquet,
        )
        _validate_max_cus_request(self.max_cus)


def _validate_checkpoint_request(value: int | None, *, has_parquet: bool) -> None:
    if value is None:
        return
    if value <= 0:
        raise ValueError("checkpoint_every_cus must be positive when provided")
    if not has_parquet:
        raise ValueError("checkpointing requires the Parquet projection")


def _validate_max_cus_request(value: int | None) -> None:
    if value is None:
        return
    if value <= 0:
        raise ValueError("max_cus must be positive when provided")


@dataclass(frozen=True, slots=True)
class MaterializedAttribute:
    """An attribute preserving raw and decoded values."""

    source_id: str
    unit_offset: int
    die_offset: int
    ordinal: int
    name: str
    form: str
    raw_value: TaggedJson
    decoded_value: TaggedJson
    value_offset: int | None = None
    indirection_length: int | None = None


@dataclass(frozen=True, slots=True)
class MaterializedUnit:
    """Compilation-unit header and source provenance."""

    source_id: str
    unit_offset: int
    unit_length: int | None
    header: dict[str, TaggedJson]
    die_offset: int | None = None
    unit_type: str | None = None
    parser_status: str | None = None
    details: TaggedJson = None


@dataclass(frozen=True, slots=True)
class MaterializedDie:
    """DIE identity and traversal evidence."""

    source_id: str
    unit_offset: int
    die_offset: int
    ordinal: int
    tag: str | None
    abbrev_code: int | None
    has_children: bool
    depth: int
    parent_offset: int | None
    is_null: bool = False


@dataclass(frozen=True, slots=True)
class MaterializedReference:
    """A raw or resolved relationship between DWARF records."""

    source_id: str
    unit_offset: int
    die_offset: int
    attribute_name: str
    relation: str
    raw_target: TaggedJson
    target_offset: int | None
    resolution_status: QueryStatus


@dataclass(frozen=True, slots=True)
class MaterializationArtifact:
    """Immutable metadata for one published analytical file."""

    path: str
    format: str
    size_bytes: int
    sha256: str
    modified_ns: int | None = None
    family: str | None = None
    compression: str | None = None
    row_group_count: int | None = None
    row_group_rows: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible artifact metadata."""
        payload = asdict(self)
        payload["row_group_rows"] = list(self.row_group_rows)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MaterializationArtifact:
        """Reconstruct one artifact descriptor from a manifest payload."""
        return cls(
            path=_artifact_string(payload, "path"),
            format=_artifact_string(payload, "format"),
            size_bytes=_artifact_required_integer(payload, "size_bytes"),
            sha256=_artifact_string(payload, "sha256"),
            modified_ns=_artifact_optional_integer(payload, "modified_ns"),
            family=_artifact_optional_string(payload, "family"),
            compression=_artifact_optional_string(payload, "compression"),
            row_group_count=_artifact_optional_integer(payload, "row_group_count"),
            row_group_rows=tuple(_artifact_rows(payload)),
        )


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Bounded query result with provenance and completeness."""

    status: QueryStatus
    items: tuple[Any, ...] = ()
    provenance: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class MaterializationManifest:
    """Atomic publication manifest for one analytical DWARF store."""

    schema_version: str
    source_path: str
    source_identity: SourceIdentity
    producer: str
    platform: str
    files: dict[str, str]
    counts: dict[str, int]
    configuration: dict[str, TaggedJson] = field(default_factory=dict)
    section_names: tuple[str, ...] = ()
    artifacts: tuple[MaterializationArtifact, ...] = ()
    status: str = "complete"

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        payload = asdict(self)
        payload["source_identity"] = self.source_identity.as_fingerprint()
        payload["section_names"] = list(self.section_names)
        payload["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MaterializationManifest:
        """Reconstruct and validate a manifest loaded from JSON."""
        identity = _manifest_identity(payload)
        files, counts = _manifest_maps(payload)
        return cls(
            schema_version=_required_string(payload, "schema_version"),
            source_path=_required_string(payload, "source_path"),
            source_identity=identity,
            producer=_required_string(payload, "producer"),
            platform=_required_string(payload, "platform"),
            files={key: str(value) for key, value in files.items()},
            counts={key: int(value) for key, value in counts.items()},
            configuration=dict(payload.get("configuration", {})),
            section_names=tuple(str(value) for value in payload.get("section_names", [])),
            artifacts=_manifest_artifacts(payload),
            status=str(payload.get("status", "complete")),
        )


def _artifact_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Materialization artifact {key} must be a non-empty string")
    return value


def _artifact_optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Materialization artifact {key} must be a string")
    return value


def _artifact_required_integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Materialization artifact {key} must be non-negative integer")
    return value


def _artifact_optional_integer(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    return _artifact_required_integer(payload, key)


def _artifact_rows(payload: dict[str, Any]) -> list[int]:
    values = payload.get("row_group_rows", [])
    if not isinstance(values, list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values
    ):
        raise ValueError("Materialization artifact row_group_rows must be non-negative integers")
    return values


def _manifest_identity(payload: dict[str, Any]) -> SourceIdentity:
    identity_payload = payload.get("source_identity")
    if not isinstance(identity_payload, dict):
        raise ValueError("Materialization manifest has no source_identity")
    return SourceIdentity(
        sha256=_required_string(identity_payload, "sha256"),
        size=_required_int(identity_payload, "size"),
        mtime_ns=_required_int(identity_payload, "mtime_ns"),
        ctime_ns=_required_int(identity_payload, "ctime_ns"),
        device=_required_int(identity_payload, "device"),
        inode=_required_int(identity_payload, "inode"),
    )


def _manifest_maps(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    files = payload.get("files", {})
    counts = payload.get("counts", {})
    if not isinstance(files, dict) or not isinstance(counts, dict):
        raise ValueError("Materialization manifest files and counts must be objects")
    return files, counts


def _manifest_artifacts(payload: dict[str, Any]) -> tuple[MaterializationArtifact, ...]:
    values = payload.get("artifacts", [])
    if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
        raise ValueError("Materialization manifest artifacts must be an array of objects")
    return tuple(MaterializationArtifact.from_dict(value) for value in values)


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Materialization manifest field {key!r} must be a non-empty string")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Materialization manifest field {key!r} must be an integer")
    return value

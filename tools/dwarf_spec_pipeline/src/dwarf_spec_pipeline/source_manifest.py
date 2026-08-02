"""Checksum-locked source acquisition for the official DWARF documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    standard_version: int = Field(ge=2, le=4)
    title: str
    filename: str
    format: Literal["mm", "doc"]
    url: str
    source_page: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    sources: list[SourceSpec]


class SourceError(RuntimeError):
    """Raised when a source cannot be downloaded or verified."""


def load_manifest(path: Path) -> SourceManifest:
    try:
        return SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceError(f"Unable to read source manifest {path}: {exc}") from exc


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source(path: Path, source: SourceSpec) -> None:
    actual = digest_file(path)
    if actual != source.sha256:
        raise SourceError(
            f"Checksum mismatch for {source.source_id}: expected {source.sha256}, got {actual}"
        )


def acquire_source(source: SourceSpec, cache_dir: Path, *, offline: bool = False) -> Path:
    destination = cache_dir / source.source_id / source.filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_source(destination, source)
        return destination
    if offline:
        raise SourceError(f"Offline mode requires cached source {destination}")

    request = Request(source.url, headers={"User-Agent": "ddon-dwarf-spec-pipeline/0.1"})
    try:
        with (
            urlopen(request, timeout=120) as response,
            tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary,
        ):
            temporary_path = Path(temporary.name)
            while chunk := response.read(1024 * 1024):
                temporary.write(chunk)
    except OSError as exc:
        raise SourceError(f"Unable to download {source.url}: {exc}") from exc

    try:
        verify_source(temporary_path, source)
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


def manifest_json(manifest: SourceManifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

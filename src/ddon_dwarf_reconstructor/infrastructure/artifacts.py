"""Durable identity for immutable reverse-engineering inputs.

DDON build inputs do not change during normal operation.  This module records
one strong SHA-256 per source and uses a cheap size/boundary fingerprint to find
that identity on later fresh-process runs, including after relocation.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, sleep, time, time_ns
from typing import Any, cast

CATALOG_SCHEMA_VERSION = "1.0"
BOUNDARY_BYTES = 64 * 1024
LOCK_TIMEOUT_SECONDS = 30.0
STALE_LOCK_SECONDS = 300.0


def get_artifact_cache_dir() -> Path:
    """Return the untracked operating-system directory for durable artifacts."""
    if explicit_cache_dir := os.getenv("DWARF_CACHE_DIR"):
        cache_dir = Path(explicit_cache_dir).expanduser()
    elif local_app_data := os.getenv("LOCALAPPDATA"):
        cache_dir = Path(local_app_data) / "ddon-dwarf-reconstructor"
    elif xdg_cache_home := os.getenv("XDG_CACHE_HOME"):
        cache_dir = Path(xdg_cache_home) / "ddon-dwarf-reconstructor"
    else:
        cache_dir = Path.home() / ".cache" / "ddon-dwarf-reconstructor"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@dataclass(frozen=True)
class SourceIdentity:
    """Strong source identity with a cheap immutable-input lookup key."""

    sha256: str
    size: int
    boundary_sha256: str

    @property
    def lookup_key(self) -> str:
        """Return the relocation-stable catalog key."""
        payload = f"{self.size}:{self.boundary_sha256}".encode()
        return hashlib.sha256(payload).hexdigest()


def probe_source(path: Path) -> tuple[int, str]:
    """Return source size and a hash of its first/last bounded regions."""
    resolved = path.resolve()
    stat = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        digest.update(source.read(BOUNDARY_BYTES))
        if stat.st_size > BOUNDARY_BYTES:
            source.seek(max(0, stat.st_size - BOUNDARY_BYTES))
            digest.update(source.read(BOUNDARY_BYTES))
    return stat.st_size, digest.hexdigest()


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SourceIdentityCatalog:
    """Persist strong identities for immutable files with atomic publication."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_artifact_cache_dir() / "source-identities-v1.json"

    def identify(self, source_path: Path, *, verify: bool = False) -> SourceIdentity:
        """Return a strong identity, hashing all bytes only when required.

        Warm reuse trusts the project's immutable-input contract after matching
        file size and both boundary regions.  ``verify=True`` forces a complete
        hash for explicit integrity checks.
        """
        resolved = source_path.resolve()
        size, boundary_sha256 = probe_source(resolved)
        lookup_key = self._lookup_key(size, boundary_sha256)
        with self._exclusive_lock():
            catalog = self._load()
            record = catalog["sources"].get(lookup_key)
            if not verify and self._valid_record(record, size, boundary_sha256):
                identity = SourceIdentity(
                    sha256=str(record["sha256"]),
                    size=size,
                    boundary_sha256=boundary_sha256,
                )
                self._remember_path(catalog, lookup_key, record, resolved)
                return identity

            identity = SourceIdentity(
                sha256=sha256_file(resolved),
                size=size,
                boundary_sha256=boundary_sha256,
            )
            paths = [] if record is None else list(record.get("paths", []))
            resolved_text = str(resolved)
            if resolved_text not in paths:
                paths.append(resolved_text)
            catalog["sources"][identity.lookup_key] = {
                **asdict(identity),
                "paths": sorted(paths),
                "verified_at_ns": time_ns(),
            }
            self._save(catalog)
            return identity

    def inspect(self, *, include_sources: bool = False) -> dict[str, Any]:
        """Return catalog metadata without hashing or changing sources."""
        catalog = self._load()
        result = {
            "path": str(self.path),
            "schema_version": catalog["schema_version"],
            "source_count": len(catalog["sources"]),
        }
        if include_sources:
            result["sources"] = catalog["sources"]
        return result

    def prune_missing_paths(self) -> dict[str, int]:
        """Remove only catalog paths that no longer exist and empty records."""
        with self._exclusive_lock():
            catalog = self._load()
            paths_removed = 0
            records_removed = 0
            for lookup_key, record in list(catalog["sources"].items()):
                existing_paths = [path for path in record.get("paths", []) if Path(path).exists()]
                paths_removed += len(record.get("paths", [])) - len(existing_paths)
                if not existing_paths:
                    del catalog["sources"][lookup_key]
                    records_removed += 1
                else:
                    record["paths"] = existing_paths
            if paths_removed:
                self._save(catalog)
        return {"paths_removed": paths_removed, "records_removed": records_removed}

    def record(self, source_path: Path, identity: SourceIdentity) -> None:
        """Record an already-established strong identity without rehashing."""
        resolved = source_path.resolve()
        size, boundary_sha256 = probe_source(resolved)
        if size != identity.size or boundary_sha256 != identity.boundary_sha256:
            raise ValueError(f"Source no longer matches supplied identity: {resolved}")
        with self._exclusive_lock():
            catalog = self._load()
            existing = catalog["sources"].get(identity.lookup_key, {})
            paths = list(existing.get("paths", [])) if isinstance(existing, dict) else []
            resolved_text = str(resolved)
            if resolved_text not in paths:
                paths.append(resolved_text)
            catalog["sources"][identity.lookup_key] = {
                **asdict(identity),
                "paths": sorted(paths),
                "verified_at_ns": time_ns(),
            }
            self._save(catalog)

    @staticmethod
    def _lookup_key(size: int, boundary_sha256: str) -> str:
        payload = f"{size}:{boundary_sha256}".encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _valid_record(record: Any, size: int, boundary_sha256: str) -> bool:
        return (
            isinstance(record, dict)
            and record.get("size") == size
            and record.get("boundary_sha256") == boundary_sha256
            and isinstance(record.get("sha256"), str)
            and len(record["sha256"]) == 64
        )

    def _remember_path(
        self, catalog: dict[str, Any], lookup_key: str, record: dict[str, Any], path: Path
    ) -> None:
        resolved_text = str(path)
        paths = list(record.get("paths", []))
        if resolved_text in paths:
            return
        record["paths"] = sorted([*paths, resolved_text])
        catalog["sources"][lookup_key] = record
        self._save(catalog)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": CATALOG_SCHEMA_VERSION, "sources": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": CATALOG_SCHEMA_VERSION, "sources": {}}
        if data.get("schema_version") != CATALOG_SCHEMA_VERSION or not isinstance(
            data.get("sources"), dict
        ):
            return {"schema_version": CATALOG_SCHEMA_VERSION, "sources": {}}
        return cast(dict[str, Any], data)

    def _save(self, catalog: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(catalog, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(self.path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        """Serialize catalog read/modify/write operations across processes."""
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                    lock_file.write(f"{os.getpid()} {time()}\n")
                break
            except FileExistsError:
                try:
                    if time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                        lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for source catalog lock: {lock_path}"
                    ) from None
                sleep(0.05)
        try:
            yield
        finally:
            with suppress(FileNotFoundError):
                lock_path.unlink()

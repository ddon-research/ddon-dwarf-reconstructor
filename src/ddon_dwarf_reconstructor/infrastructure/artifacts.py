"""Durable identity for immutable reverse-engineering inputs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, sleep, time, time_ns
from typing import Any, cast

from ..core.observability import get_logger, log_event
from ..domain.ports.source_identity import SourceIdentity, source_metadata_lookup_key

CATALOG_SCHEMA_VERSION = "1.0"
LOCK_TIMEOUT_SECONDS = 30.0
STALE_LOCK_SECONDS = 300.0
logger = get_logger(__name__)


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
class SourceMetadata:
    """Filesystem metadata used to decide whether a cached strong hash is current."""

    size: int
    mtime_ns: int
    ctime_ns: int
    device: int
    inode: int

    @property
    def lookup_key(self) -> str:
        """Return a relocation-stable key for an unchanged filesystem object."""
        return source_metadata_lookup_key(self.size, self.mtime_ns, self.device, self.inode)


def probe_source(path: Path) -> SourceMetadata:
    """Return metadata sufficient to detect ordinary source replacement."""
    resolved = path.resolve()
    stat = resolved.stat()
    return SourceMetadata(
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        ctime_ns=stat.st_ctime_ns,
        device=stat.st_dev,
        inode=stat.st_ino,
    )


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
        """Return a strong identity, hashing all bytes only when metadata changes."""
        resolved = source_path.resolve()
        metadata = probe_source(resolved)
        lookup_key = metadata.lookup_key
        with self._exclusive_lock():
            catalog = self._load()
            record_key, record = self._locate_record(catalog, lookup_key, metadata, resolved)
            if record is not None and self._can_reuse(record, metadata, resolved, verify):
                identity = self._identity_from_record(record)
                self._publish_cache_hit(
                    catalog, record_key, lookup_key, record, resolved, metadata, identity
                )
                return identity

            return self._rehash_and_store(catalog, record_key, record, resolved, metadata, verify)

    def sha256(self, source_path: Path) -> str:
        """Implement the application source-hash port with durable warm reuse."""
        return self.identify(source_path).sha256

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
        metadata = probe_source(resolved)
        with self._exclusive_lock():
            catalog = self._load()
            record_key, existing = self._locate_record(
                catalog, identity.lookup_key, metadata, resolved
            )
            if not self._identity_metadata_matches(identity, metadata) and not (
                isinstance(existing, dict)
                and existing.get("sha256") == identity.sha256
                and self._valid_record(existing, metadata, resolved)
            ):
                raise ValueError(f"Source no longer matches supplied identity: {resolved}")
            stored_record = existing if isinstance(existing, dict) else {}
            paths = self._record_paths(stored_record)
            resolved_text = str(resolved)
            if resolved_text not in paths:
                paths.append(resolved_text)
            self._rekey_record(catalog, record_key, identity.lookup_key, stored_record)
            catalog["sources"][identity.lookup_key] = {
                **asdict(identity),
                "paths": sorted(paths),
                "verified_at_ns": time_ns(),
            }
            self._save(catalog)

    @staticmethod
    def _identity_metadata_matches(identity: SourceIdentity, metadata: SourceMetadata) -> bool:
        return all(
            getattr(identity, key) == getattr(metadata, key)
            for key in ("size", "mtime_ns", "ctime_ns", "device", "inode")
        )

    @classmethod
    def _can_reuse(
        cls,
        record: dict[str, Any],
        metadata: SourceMetadata,
        source_path: Path,
        verify: bool,
    ) -> bool:
        if verify:
            return False
        return cls._valid_record(record, metadata, source_path)

    def _publish_cache_hit(
        self,
        catalog: dict[str, Any],
        record_key: str | None,
        lookup_key: str,
        record: dict[str, Any],
        source_path: Path,
        metadata: SourceMetadata,
        identity: SourceIdentity,
    ) -> None:
        catalog_changed = self._rekey_record(catalog, record_key, lookup_key, record)
        catalog_changed = (
            self._remember_path(catalog, lookup_key, record, source_path) or catalog_changed
        )
        if catalog_changed:
            self._save(catalog)
        log_event(
            logger,
            logging.DEBUG,
            "source_identity_cache_hit",
            source_path=source_path,
            source_size=metadata.size,
            source_sha256=identity.sha256,
            verified=False,
            relocated=identity.ctime_ns != metadata.ctime_ns,
        )

    def _rehash_and_store(
        self,
        catalog: dict[str, Any],
        record_key: str | None,
        record: dict[str, Any] | None,
        source_path: Path,
        metadata: SourceMetadata,
        verify: bool,
    ) -> SourceIdentity:
        identity = SourceIdentity(sha256=sha256_file(source_path), **asdict(metadata))
        paths = self._record_paths(record)
        resolved_text = str(source_path)
        if resolved_text not in paths:
            paths.append(resolved_text)
        if record_key is not None and record_key != identity.lookup_key:
            catalog["sources"].pop(record_key, None)
        catalog["sources"][identity.lookup_key] = {
            **asdict(identity),
            "paths": sorted(paths),
            "verified_at_ns": time_ns(),
        }
        self._save(catalog)
        log_event(
            logger,
            logging.INFO,
            "source_identity_rehashed",
            source_path=source_path,
            source_size=metadata.size,
            source_sha256=identity.sha256,
            verified=verify,
        )
        return identity

    @staticmethod
    def _record_paths(record: dict[str, Any] | None) -> list[str]:
        if not isinstance(record, dict) or not isinstance(record.get("paths"), list):
            return []
        return [path for path in record["paths"] if isinstance(path, str)]

    @staticmethod
    def _stable_metadata_matches(record: dict[str, Any], metadata: SourceMetadata) -> bool:
        return all(
            record.get(key) == getattr(metadata, key)
            for key in ("size", "mtime_ns", "device", "inode")
        )

    @staticmethod
    def _is_relocated(record: dict[str, Any], source_path: Path) -> bool:
        paths = record.get("paths")
        if not isinstance(paths, list):
            return False
        resolved_text = str(source_path)
        return resolved_text not in paths and any(
            isinstance(path, str) and not Path(path).exists() for path in paths
        )

    @classmethod
    def _valid_record(cls, record: Any, metadata: SourceMetadata, source_path: Path) -> bool:
        return (
            isinstance(record, dict)
            and cls._stable_metadata_matches(record, metadata)
            and isinstance(record.get("sha256"), str)
            and len(record["sha256"]) == 64
            and (
                record.get("ctime_ns") == metadata.ctime_ns
                or cls._is_relocated(record, source_path)
            )
        )

    @staticmethod
    def _identity_from_record(record: dict[str, Any]) -> SourceIdentity:
        return SourceIdentity(
            sha256=str(record["sha256"]),
            size=int(record["size"]),
            mtime_ns=int(record["mtime_ns"]),
            ctime_ns=int(record["ctime_ns"]),
            device=int(record["device"]),
            inode=int(record["inode"]),
        )

    def _locate_record(
        self,
        catalog: dict[str, Any],
        lookup_key: str,
        metadata: SourceMetadata,
        source_path: Path,
    ) -> tuple[str | None, dict[str, Any] | None]:
        direct = catalog["sources"].get(lookup_key)
        if lookup_key in catalog["sources"]:
            return lookup_key, direct if isinstance(direct, dict) else None
        for candidate_key in sorted(catalog["sources"]):
            candidate = catalog["sources"][candidate_key]
            if isinstance(candidate, dict) and self._valid_record(candidate, metadata, source_path):
                return candidate_key, candidate
        return None, None

    @staticmethod
    def _rekey_record(
        catalog: dict[str, Any],
        record_key: str | None,
        lookup_key: str,
        record: dict[str, Any],
    ) -> bool:
        if record_key is None or record_key == lookup_key:
            return False
        catalog["sources"][lookup_key] = record
        catalog["sources"].pop(record_key, None)
        return True

    def _remember_path(
        self, catalog: dict[str, Any], lookup_key: str, record: dict[str, Any], path: Path
    ) -> bool:
        resolved_text = str(path)
        paths = self._record_paths(record)
        if resolved_text in paths:
            return False
        record["paths"] = sorted([*paths, resolved_text])
        catalog["sources"][lookup_key] = record
        return True

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": CATALOG_SCHEMA_VERSION, "sources": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_event(
                logger,
                logging.WARNING,
                "source_identity_catalog_unreadable",
                catalog_path=self.path,
                exc_info=error,
            )
            return {"schema_version": CATALOG_SCHEMA_VERSION, "sources": {}}
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != CATALOG_SCHEMA_VERSION
            or not isinstance(data.get("sources"), dict)
        ):
            log_event(
                logger,
                logging.WARNING,
                "source_identity_catalog_invalid",
                catalog_path=self.path,
            )
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
            log_event(
                logger,
                logging.DEBUG,
                "source_identity_catalog_published",
                catalog_path=self.path,
                source_count=len(catalog["sources"]),
            )
        finally:
            temporary_path.unlink(missing_ok=True)

    @contextmanager
    def _exclusive_lock(self) -> Generator[None]:
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
                        log_event(
                            logger,
                            logging.WARNING,
                            "source_identity_stale_lock_removed",
                            lock_path=lock_path,
                        )
                        continue
                except FileNotFoundError:
                    continue
                if monotonic() >= deadline:
                    log_event(
                        logger,
                        logging.ERROR,
                        "source_identity_lock_timeout",
                        lock_path=lock_path,
                    )
                    raise TimeoutError(
                        f"Timed out waiting for source catalog lock: {lock_path}"
                    ) from None
                sleep(0.05)
        try:
            yield
        finally:
            with suppress(FileNotFoundError):
                lock_path.unlink()

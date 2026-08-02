#!/usr/bin/env python3

"""Durable, streaming index façade for compressed LLVM DWARF dumps."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Generator
from contextlib import closing, contextmanager, suppress
from pathlib import Path
from time import monotonic, sleep, time

from ..core.observability import get_logger
from ..infrastructure.artifacts import SourceIdentityCatalog
from .zstd_dump_query import DefinitionLocation as DefinitionLocation
from .zstd_dump_query import ZstdDumpQueryMixin
from .zstd_dump_scan import ZstdDumpScanMixin

logger = get_logger(__name__)

INDEX_SCHEMA_VERSION = "1.2"
INDEX_PRODUCER = "ddon-dwarf-zstd-index"
INDEX_PRODUCER_VERSION = "1"
INDEX_CONFIG_SHA256 = hashlib.sha256(
    b"class-definition-v1|method-implementation-v1|llvm-dwarfdump-text"
).hexdigest()
LOCK_TIMEOUT_SECONDS = 30.0
STALE_LOCK_SECONDS = 300.0


class ZstdDumpParser(ZstdDumpQueryMixin, ZstdDumpScanMixin):
    """Manage a source-bound SQLite sidecar built by one streaming pass."""

    INDEX_SCHEMA_VERSION = INDEX_SCHEMA_VERSION
    INDEX_PRODUCER = INDEX_PRODUCER
    INDEX_PRODUCER_VERSION = INDEX_PRODUCER_VERSION
    INDEX_CONFIG_SHA256 = INDEX_CONFIG_SHA256

    def __init__(self, dump_path: Path, index_path: Path | None = None):
        self.dump_path = Path(dump_path)
        if not self.dump_path.exists():
            raise FileNotFoundError(f"DWARF dump not found: {self.dump_path}")
        self.index_path = (
            Path(index_path)
            if index_path
            else self.dump_path.with_name(f"{self.dump_path.name}.index.sqlite3")
        )

    def _ensure_index(self, *, force: bool = False) -> None:
        source_metadata = self._source_metadata()
        if not force and self._index_matches_source(source_metadata):
            self._enrich_metadata(source_metadata)
            return
        with self._exclusive_lock():
            if not force and self._index_matches_source(source_metadata):
                self._enrich_metadata(source_metadata)
                return
            self._build_index(source_metadata)

    def _build_index(self, source_metadata: dict[str, str]) -> None:
        """Build a temporary sidecar and publish it atomically."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.index_path.name}.", suffix=".tmp", dir=self.index_path.parent
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(temporary_path)
            self._create_schema(connection)
            self._scan_dump(connection)
            self._write_metadata(connection, source_metadata)
            connection.commit()
            connection.close()
            connection = None
            temporary_path.replace(self.index_path)
        finally:
            if connection is not None:
                connection.close()
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE class_definitions (
                name TEXT NOT NULL, cu_offset TEXT NOT NULL, die_offset TEXT NOT NULL,
                nested_enum_count INTEGER NOT NULL, nested_struct_count INTEGER NOT NULL,
                nested_union_count INTEGER NOT NULL, byte_size INTEGER NOT NULL,
                completeness_score INTEGER NOT NULL,
                PRIMARY KEY (name, die_offset)
            );
            CREATE INDEX class_definitions_name_idx ON class_definitions(name);
            CREATE TABLE method_implementations (
                declaration_offset INTEGER PRIMARY KEY,
                implementation_offset INTEGER NOT NULL
            );
            """
        )

    def _source_metadata(self) -> dict[str, str]:
        identity = SourceIdentityCatalog().identify(self.dump_path)
        return {
            "source_sha256": identity.sha256,
            "source_size": str(identity.size),
        }

    def _index_matches_source(self, source_metadata: dict[str, str]) -> bool:
        if not self.index_path.exists():
            return False
        metadata = self._read_metadata()
        if metadata is None or metadata.get("schema_version") not in {"1.1", INDEX_SCHEMA_VERSION}:
            return False
        return self._has_required_tables() and self._metadata_matches_source(
            metadata, source_metadata
        )

    @staticmethod
    def _metadata_matches_source(metadata: dict[str, str], source_metadata: dict[str, str]) -> bool:
        for key in ("source_size", "source_sha256"):
            stored = metadata.get(key)
            if stored is not None and stored != source_metadata[key]:
                return False
        return True

    def _enrich_metadata(self, source_metadata: dict[str, str]) -> None:
        if not self.index_path.exists() or not self._has_required_tables():
            return
        with closing(self._connect_index()) as connection:
            self._write_metadata(connection, source_metadata)
            connection.commit()

    def _write_metadata(
        self, connection: sqlite3.Connection, source_metadata: dict[str, str]
    ) -> None:
        metadata = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "producer": INDEX_PRODUCER,
            "producer_version": INDEX_PRODUCER_VERSION,
            "config_sha256": INDEX_CONFIG_SHA256,
            **source_metadata,
        }
        connection.executemany(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )

    def _read_metadata(self) -> dict[str, str] | None:
        try:
            with closing(self._connect_index()) as connection:
                rows = connection.execute("SELECT key, value FROM metadata").fetchall()
            return {str(key): str(value) for key, value in rows}
        except sqlite3.DatabaseError:
            return None

    def _has_required_tables(self) -> bool:
        try:
            with closing(self._connect_index()) as connection:
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            return {"metadata", "class_definitions", "method_implementations"}.issubset(tables)
        except sqlite3.DatabaseError:
            return False

    def _connect_index(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.index_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _exclusive_lock(self) -> Generator[None]:
        """Serialize sidecar publication and recover abandoned locks."""
        lock_path = self.index_path.with_suffix(f"{self.index_path.suffix}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = monotonic() + LOCK_TIMEOUT_SECONDS
        self._acquire_lock(lock_path, deadline)
        try:
            yield
        finally:
            with suppress(FileNotFoundError):
                lock_path.unlink()

    @staticmethod
    def _acquire_lock(lock_path: Path, deadline: float) -> None:
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                    lock_file.write(f"{os.getpid()} {time()}\n")
                return
            except FileExistsError:
                if ZstdDumpParser._remove_stale_lock(lock_path):
                    continue
                if monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for dump index lock: {lock_path}"
                    ) from None
                sleep(0.05)

    @staticmethod
    def _remove_stale_lock(lock_path: Path) -> bool:
        try:
            if time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                lock_path.unlink()
                return True
        except FileNotFoundError:
            return True
        return False

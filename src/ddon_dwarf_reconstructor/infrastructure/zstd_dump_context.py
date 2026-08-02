"""Typed collaboration contract for the compressed-DWARF sidecar façade."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .zstd_dump_scan import _DumpScanState


class ZstdDumpContext(Protocol):
    """State and operations shared by sidecar query and scan stages."""

    dump_path: Path
    index_path: Path
    INDEX_SCHEMA_VERSION: str
    INDEX_PRODUCER: str
    INDEX_PRODUCER_VERSION: str
    INDEX_CONFIG_SHA256: str

    def _ensure_index(self, *, force: bool = False) -> None: ...

    def _connect_index(self) -> sqlite3.Connection: ...

    def _read_metadata(self) -> dict[str, str] | None: ...

    def _source_metadata(self) -> dict[str, str]: ...

    def _metadata_matches_source(
        self, metadata: dict[str, str], source_metadata: dict[str, str]
    ) -> bool: ...

    def _scan_dump(self, connection: sqlite3.Connection) -> None: ...

    def _scan_line(
        self, connection: sqlite3.Connection, state: _DumpScanState, line: str
    ) -> None: ...

    def _insert_class_records(
        self,
        connection: sqlite3.Connection,
        records: dict[str, dict[str, int | str]],
    ) -> None: ...

    @staticmethod
    def _definition_from_row(row: tuple[object, ...]) -> object: ...

    def inspect_index(self) -> dict[str, object]: ...

    def _exclusive_lock(self) -> AbstractContextManager[None]: ...

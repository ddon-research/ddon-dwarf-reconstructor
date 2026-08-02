"""Read-only query operations for the compressed-DWARF sidecar."""

from __future__ import annotations

import logging
from contextlib import closing
from dataclasses import dataclass
from typing import cast

from .logging import get_logger, log_event
from .zstd_dump_context import ZstdDumpContext

logger = get_logger(__name__)


@dataclass(frozen=True)
class DefinitionLocation:
    """DWARF definition location with completeness metrics."""

    cu_offset: str
    die_offset: str
    nested_enum_count: int
    nested_struct_count: int
    nested_union_count: int
    byte_size: int
    completeness_score: int


class ZstdDumpQueryMixin:
    def find_class_definitions(self: ZstdDumpContext, class_name: str) -> list[DefinitionLocation]:
        """Return all indexed definitions for a class in deterministic order."""
        self._ensure_index()
        with closing(self._connect_index()) as connection:
            rows = connection.execute(
                """
                SELECT cu_offset, die_offset, nested_enum_count,
                       nested_struct_count, nested_union_count, byte_size,
                       completeness_score
                FROM class_definitions
                WHERE name = ?
                ORDER BY completeness_score DESC,
                         nested_enum_count DESC,
                         nested_struct_count DESC,
                         nested_union_count DESC,
                         byte_size DESC,
                         CAST(die_offset AS INTEGER) ASC
                """,
                (class_name,),
            ).fetchall()
        definitions = [cast(DefinitionLocation, self._definition_from_row(row)) for row in rows]
        best_score = definitions[0].completeness_score if definitions else 0
        log_event(
            logger,
            logging.DEBUG,
            "dwarf_dump_definitions_found",
            class_name=class_name,
            definition_count=len(definitions),
            best_score=best_score,
        )
        return definitions

    @staticmethod
    def _definition_from_row(row: tuple[object, ...]) -> DefinitionLocation:
        return DefinitionLocation(
            cu_offset=str(row[0]),
            die_offset=f"0x{_as_int(row[1]):x}",
            nested_enum_count=_as_int(row[2]),
            nested_struct_count=_as_int(row[3]),
            nested_union_count=_as_int(row[4]),
            byte_size=_as_int(row[5]),
            completeness_score=_as_int(row[6]),
        )

    def find_method_implementation(self: ZstdDumpContext, declaration_offset: int) -> int | None:
        """Return an indexed implementation DIE offset for a declaration."""
        self._ensure_index()
        with closing(self._connect_index()) as connection:
            row = connection.execute(
                """
                SELECT implementation_offset
                FROM method_implementations
                WHERE declaration_offset = ?
                """,
                (declaration_offset,),
            ).fetchone()
        return _as_int(row[0]) if row is not None else None

    def inspect_index(self: ZstdDumpContext) -> dict[str, object]:
        """Return sidecar status without building a missing index."""
        result: dict[str, object] = {
            "path": str(self.index_path.resolve()),
            "exists": self.index_path.exists(),
        }
        if not self.index_path.exists():
            result["status"] = "missing"
            return result
        metadata = self._read_metadata()
        if metadata is None:
            result["status"] = "invalid"
            return result
        result["metadata"] = metadata
        try:
            source_metadata = self._source_metadata()
            result["status"] = (
                "ready" if self._metadata_matches_source(metadata, source_metadata) else "stale"
            )
        except OSError as error:
            log_event(
                logger,
                logging.WARNING,
                "dwarf_dump_index_inspection_failed",
                index_path=self.index_path,
                exc_info=error,
            )
            result["status"] = "unavailable"
            result["error"] = str(error)
        return result

    def repair_index(self: ZstdDumpContext) -> dict[str, object]:
        """Repair or create the sidecar while preserving valid indexed data."""
        self._ensure_index()
        return {"action": "repair", **self.inspect_index()}

    def rebuild_index(self: ZstdDumpContext) -> dict[str, object]:
        """Force a fresh streaming scan and atomic sidecar replacement."""
        self._ensure_index(force=True)
        return {"action": "rebuild", **self.inspect_index()}


def _as_int(value: object) -> int:
    """Convert SQLite scalar values while rejecting malformed sidecar data."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        value = value.decode("ascii")
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return int(value, 16)
    raise TypeError(f"Expected an integer sidecar value, got {type(value).__name__}")

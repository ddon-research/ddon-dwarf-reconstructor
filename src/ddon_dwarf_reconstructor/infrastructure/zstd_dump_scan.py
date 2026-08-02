"""One-pass streaming scan state for compressed LLVM DWARF dumps."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from re import Pattern
from time import perf_counter

from .logging import get_logger, log_event
from .zstd_dump_context import ZstdDumpContext

logger = get_logger(__name__)


@dataclass(frozen=True)
class _DumpPatterns:
    cu: Pattern[str]
    class_die: Pattern[str]
    subprogram: Pattern[str]
    name: Pattern[str]
    size: Pattern[str]
    enum: Pattern[str]
    struct: Pattern[str]
    union: Pattern[str]
    specification: Pattern[str]

    @classmethod
    def create(cls) -> _DumpPatterns:
        flags = re.IGNORECASE
        return cls(
            re.compile(r"^(0x[0-9a-f]+):\s+Compile Unit:", flags),
            re.compile(r"^(0x[0-9a-f]+):\s+DW_TAG_class_type.*\((0x[0-9a-f]+)\)", flags),
            re.compile(r"^(0x[0-9a-f]+):\s+DW_TAG_subprogram", flags),
            re.compile(r'DW_AT_name.*["\']([^"\']+)["\']'),
            re.compile(r"DW_AT_byte_size.*\(0x([0-9a-f]+)\)", flags),
            re.compile(r"DW_TAG_enumeration_type.*\*\s*\((0x[0-9a-f]+)\)", flags),
            re.compile(r"DW_TAG_structure_type.*\*\s*\((0x[0-9a-f]+)\)", flags),
            re.compile(r"DW_TAG_union_type.*\*\s*\((0x[0-9a-f]+)\)", flags),
            re.compile(
                r"DW_AT_specification.*?(?:\(\s*0x([0-9a-f]+)\s*\)|\{\s*0x([0-9a-f]+)\s*\})",
                flags,
            ),
        )


@dataclass
class _DumpScanState:
    patterns: _DumpPatterns
    class_records: dict[str, dict[str, int | str]]
    current_cu_offset: str | None = None
    current_class_die: str | None = None
    current_class_record: dict[str, int | str] | None = None
    current_subprogram_offset: int | None = None


class ZstdDumpScanMixin:
    def _scan_dump(self: ZstdDumpContext, connection: sqlite3.Connection) -> None:
        """Stream the compressed dump once without materializing its text."""
        import compression.zstd as zstd

        started_at = perf_counter()
        state = _DumpScanState(_DumpPatterns.create(), {})
        with zstd.open(str(self.dump_path), "rt", encoding="utf-8", errors="replace") as stream:
            for raw_line in stream:
                self._scan_line(connection, state, raw_line.rstrip("\r\n"))
        self._insert_class_records(connection, state.class_records)
        log_event(
            logger,
            logging.INFO,
            "dwarf_dump_scan_completed",
            dump_path=self.dump_path,
            class_records=len(state.class_records),
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )

    def _scan_line(
        self,
        connection: sqlite3.Connection,
        state: _DumpScanState,
        line: str,
    ) -> None:
        if self._scan_header(state, line):
            return
        self._scan_line_body(connection, state, line)

    def _scan_header(self, state: _DumpScanState, line: str) -> bool:
        if "Compile Unit:" in line and self._scan_cu_header(state, line):
            return True
        if "DW_TAG_class_type" in line and self._scan_class_header(state, line):
            return True
        return "DW_TAG_subprogram" in line and self._scan_subprogram_header(state, line)

    def _scan_line_body(
        self,
        connection: sqlite3.Connection,
        state: _DumpScanState,
        line: str,
    ) -> None:
        if state.current_subprogram_offset is not None and "DW_AT_specification" in line:
            self._scan_method_specification(connection, state, line)
        record = state.current_class_record
        if record is not None and (
            "DW_AT_name" in line
            or "DW_AT_byte_size" in line
            or "DW_TAG_enumeration_type" in line
            or "DW_TAG_structure_type" in line
            or "DW_TAG_union_type" in line
        ):
            self._scan_class_attributes(record, state.patterns, line)

    def _scan_cu_header(self, state: _DumpScanState, line: str) -> bool:
        match = state.patterns.cu.match(line)
        if match is None:
            return False
        state.current_cu_offset = self._normalize_hex(match.group(1))
        state.current_class_die = None
        state.current_class_record = None
        state.current_subprogram_offset = None
        return True

    def _scan_class_header(self, state: _DumpScanState, line: str) -> bool:
        match = state.patterns.class_die.match(line)
        if match is None:
            return False
        die_offset = self._normalize_hex(match.group(1))
        parent_offset = self._normalize_hex(match.group(2))
        record: dict[str, int | str] = {
            "name": "",
            "cu_offset": state.current_cu_offset or parent_offset,
            "die_offset": die_offset,
            "byte_size": 0,
            "nested_enums": 0,
            "nested_structs": 0,
            "nested_unions": 0,
        }
        state.class_records[die_offset] = record
        state.current_class_die = die_offset
        state.current_class_record = record
        state.current_subprogram_offset = None
        return True

    @staticmethod
    def _scan_subprogram_header(state: _DumpScanState, line: str) -> bool:
        match = state.patterns.subprogram.match(line)
        if match is None:
            return False
        state.current_subprogram_offset = int(match.group(1), 16)
        return True

    def _scan_method_specification(
        self,
        connection: sqlite3.Connection,
        state: _DumpScanState,
        line: str,
    ) -> None:
        if state.current_subprogram_offset is None:
            return
        match = state.patterns.specification.search(line)
        if match is None:
            return
        declaration_text = match.group(1) or match.group(2)
        if declaration_text is not None:
            connection.execute(
                """
                INSERT OR REPLACE INTO method_implementations(
                    declaration_offset, implementation_offset
                ) VALUES (?, ?)
                """,
                (int(declaration_text, 16), state.current_subprogram_offset),
            )
        state.current_subprogram_offset = None

    def _scan_class_attributes(
        self,
        record: dict[str, int | str],
        patterns: _DumpPatterns,
        line: str,
    ) -> None:
        if "DW_AT_name" in line and not record["name"]:
            name_match = patterns.name.search(line)
            if name_match:
                record["name"] = name_match.group(1)
        if "DW_AT_byte_size" in line:
            size_match = patterns.size.search(line)
            if size_match:
                record["byte_size"] = int(size_match.group(1), 16)
        self._scan_nested_counts(record, patterns, line)

    @staticmethod
    def _scan_nested_counts(
        record: dict[str, int | str], patterns: _DumpPatterns, line: str
    ) -> None:
        if "DW_TAG_enumeration_type" in line:
            ZstdDumpScanMixin._increment_nested_count(record, patterns.enum, line, "nested_enums")
        if "DW_TAG_structure_type" in line:
            ZstdDumpScanMixin._increment_nested_count(
                record, patterns.struct, line, "nested_structs"
            )
        if "DW_TAG_union_type" in line:
            ZstdDumpScanMixin._increment_nested_count(record, patterns.union, line, "nested_unions")

    def _insert_class_records(
        self,
        connection: sqlite3.Connection,
        records: dict[str, dict[str, int | str]],
    ) -> None:
        for record in records.values():
            if record["name"]:
                self._insert_class_record(connection, record)

    def _insert_class_record(
        self, connection: sqlite3.Connection, record: dict[str, int | str]
    ) -> None:
        byte_size = int(record["byte_size"])
        nested_enums = int(record["nested_enums"])
        nested_structs = int(record["nested_structs"])
        nested_unions = int(record["nested_unions"])
        score = byte_size + nested_enums * 1000 + nested_structs * 500 + nested_unions * 300
        connection.execute(
            """
            INSERT INTO class_definitions(
                name, cu_offset, die_offset, nested_enum_count,
                nested_struct_count, nested_union_count, byte_size,
                completeness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record["name"]),
                str(record["cu_offset"]),
                str(int(str(record["die_offset"]), 16)),
                nested_enums,
                nested_structs,
                nested_unions,
                byte_size,
                score,
            ),
        )

    @staticmethod
    def _normalize_hex(value: str) -> str:
        return f"{int(value, 16):x}"

    @staticmethod
    def _increment_nested_count(
        record: dict[str, int | str],
        pattern: Pattern[str],
        line: str,
        field_name: str,
    ) -> None:
        """Increment a nested-type counter when its parent is this class."""
        match = pattern.search(line)
        if match and ZstdDumpScanMixin._normalize_hex(match.group(1)) == record["die_offset"]:
            record[field_name] = int(record[field_name]) + 1

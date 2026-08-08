"""Small row-backed models shared by JSONL and Parquet query adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .json_codec import untag_value


@dataclass(slots=True)
class DieData:
    """Materialized DIE state retained by the JSONL compatibility adapter."""

    unit_offset: int
    die_offset: int
    ordinal: int
    tag: str | None
    abbrev_code: int | None
    has_children: bool
    depth: int
    parent_offset: int | None
    is_null: bool
    attributes: dict[str, dict[str, Any]]


class StoreAttribute:
    """pyelftools-compatible attribute view backed by a typed row."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.form = str(record.get("form", ""))
        self.value = untag_value(record.get("decoded_value"))
        self.raw_value = untag_value(record.get("raw_value"))
        self.offset = record.get("value_offset")
        self.indirection_length = record.get("indirection_length")

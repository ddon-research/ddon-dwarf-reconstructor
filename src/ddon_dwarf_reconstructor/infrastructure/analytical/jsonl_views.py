"""Generator-compatible views over a materialized analytical store."""

# The names intentionally mirror the pyelftools protocol at this adapter boundary.
# ruff: noqa: N802

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import NestedTypeCounts
from .json_codec import untag_value
from .jsonl_models import DieData, StoreAttribute
from .line_program import StoreLineProgram
from .materialized_views import MaterializedQueryPort, MaterializedStorePort


class StoreCompilationUnit:
    """Generator-compatible compilation unit reconstructed from store rows."""

    def __init__(self, store: MaterializedStorePort, record: dict[str, Any]) -> None:
        self._store = store
        self.cu_offset = int(record.get("unit_offset", 0))
        self.header = untag_value(record.get("header", {}))
        if not isinstance(self.header, dict):
            self.header = {}
        self.dwarfinfo = store.dwarf_info

    def iter_DIEs(self) -> Iterable[StoreDie]:
        return self._store.dies_for_unit(self.cu_offset)

    def get_top_DIE(self) -> StoreDie:
        for die in self.iter_DIEs():
            if not die.is_null() and die.depth == 0:
                return die
        raise ValueError(f"Compilation unit 0x{self.cu_offset:x} has no top DIE")

    def __getitem__(self, key: str) -> Any:
        return self.header[key]


class StoreDie:
    """Generator-compatible DIE reconstructed from normalized records."""

    def __init__(self, store: MaterializedStorePort, data: DieData) -> None:
        self._store = store
        self._data = data
        self.tag = data.tag
        self.offset = data.die_offset
        self.has_children = data.has_children
        self.attributes = {name: StoreAttribute(record) for name, record in data.attributes.items()}
        self.cu = store.compilation_unit_by_offset(data.unit_offset)
        self.dwarfinfo = store.dwarf_info
        self.depth = data.depth

    def __getitem__(self, attribute_name: str) -> StoreAttribute:
        return self.attributes[attribute_name]

    def get_DIE_from_attribute(self, attribute_name: str) -> StoreDie | None:
        target_offset = self._store.attribute_target(self.offset, attribute_name)
        if target_offset is None:
            return None
        return self._store.die_by_offset(target_offset)

    def get_full_path(self) -> str:
        names: list[str] = []
        current: StoreDie | None = self
        while current is not None:
            attribute = current.attributes.get("DW_AT_name")
            if attribute is not None:
                names.append(_text(attribute.value))
            current = current.get_parent()
        return "::".join(reversed([name for name in names if name]))

    def get_parent(self) -> StoreDie | None:
        parent_offset = self._data.parent_offset
        return self._store.die_by_offset(parent_offset) if parent_offset is not None else None

    def iter_children(self) -> Iterable[StoreDie]:
        return self._store.children_for_die(self.offset)

    def is_null(self) -> bool:
        return self._data.is_null

    def child_tag_counts(self) -> NestedTypeCounts:
        """Return ranking counts through the store view boundary."""
        return self._store.child_tag_counts(self.offset)


class _EmptyLineProgram:
    """Explicit empty line-program view when line records are unavailable."""

    header: dict[str, list[Any]] = {"file_entry": []}


class StoreDwarfInfo:
    """DwarfInfo protocol implemented by the materialized store."""

    def __init__(self, store: MaterializedStorePort) -> None:
        self._store = store

    def iter_CUs(self) -> Iterable[StoreCompilationUnit]:
        return self._store.iter_dwarf_units()

    def get_DIE_from_refaddr(self, refaddr: int, cu: Any = None) -> StoreDie | None:
        del cu
        return self._store.die_by_offset(refaddr)

    def line_program_for_CU(self, CU: Any) -> StoreLineProgram | _EmptyLineProgram:  # noqa: N803
        program = self._store.line_program_for_unit(int(CU.cu_offset))
        return program if program is not None else _EmptyLineProgram()


class _MaterializedCache(SymbolCachePort):
    """Non-persistent cache view because the store itself is already durable."""

    def __init__(self, store: MaterializedQueryPort) -> None:
        self._store = store

    def get_symbol_offset(self, symbol_name: str) -> int | None:
        result = self._store.find_definitions(symbol_name)
        item = result.items[0] if result.items else None
        return item.offset if isinstance(item, StoreDie) else None

    def get_symbol_cu_offset(self, symbol_name: str) -> int | None:
        result = self._store.find_definitions(symbol_name)
        item = result.items[0] if result.items else None
        return item.cu.cu_offset if isinstance(item, StoreDie) else None

    def get_symbol_completeness(self, symbol_name: str) -> bool | None:
        result = self._store.find_definitions(symbol_name)
        if not result.items:
            return None
        return _is_complete_definition(result.items[0])

    def add_symbol(self, symbol_name: str, offset: int) -> None:
        del symbol_name, offset

    def add_symbol_cu_mapping(
        self,
        symbol_name: str,
        cu_offset: int,
        die_offset: int,
        score: int = 0,
        complete: bool = True,
    ) -> None:
        del symbol_name, cu_offset, die_offset, score, complete

    def save(self) -> None:
        return

    def get_statistics(self) -> dict[str, Any]:
        return {"backend": "materialized-jsonl", "durable": True}


def _is_complete_definition(die: StoreDie) -> bool:
    return "DW_AT_declaration" not in die.attributes


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""

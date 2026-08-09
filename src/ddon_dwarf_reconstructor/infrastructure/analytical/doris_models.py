"""Generator-compatible views over rows served by Doris."""

# The names intentionally mirror the pyelftools protocol at this adapter boundary.
# ruff: noqa: N802

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from ...core.dwarf import DwarfInfo
from .json_codec import untag_value
from .line_program import StoreLineProgram


class DorisStoreView(Protocol):
    """Operations needed by generator-facing Doris record views."""

    dwarf_info: DwarfInfo

    def dies_for_unit(self, unit_offset: int) -> Iterable[DorisDie]: ...

    def compilation_unit_by_offset(self, unit_offset: int) -> DorisCompilationUnit: ...

    def die_by_offset(self, die_offset: int | None) -> DorisDie | None: ...

    def attribute_target(self, die_offset: int, attribute_name: str) -> int | None: ...

    def children_for_die(self, die_offset: int) -> Iterable[DorisDie]: ...

    def line_program_for_unit(self, unit_offset: int) -> StoreLineProgram | None: ...

    def iter_dwarf_units(self) -> Iterable[DorisCompilationUnit]: ...


class DorisCompilationUnit:
    """Compilation unit reconstructed from one Doris unit row."""

    def __init__(self, store: DorisStoreView, record: Mapping[str, Any]) -> None:
        self._store = store
        self.cu_offset = int(record.get("unit_offset", 0))
        header = record.get("header", {})
        self.header = header if isinstance(header, dict) else {}
        self.dwarfinfo = store.dwarf_info

    def iter_DIEs(self) -> Iterable[DorisDie]:
        return self._store.dies_for_unit(self.cu_offset)

    def get_top_DIE(self) -> DorisDie:
        for die in self.iter_DIEs():
            if not die.is_null() and die.depth == 0:
                return die
        raise ValueError(f"Compilation unit 0x{self.cu_offset:x} has no top DIE")

    def __getitem__(self, key: str) -> Any:
        return self.header[key]


class DorisAttribute:
    """pyelftools-compatible attribute view backed by one typed row."""

    def __init__(self, record: Mapping[str, Any]) -> None:
        self.form = str(record.get("form", ""))
        self.value = untag_value(record.get("decoded_value"))
        self.raw_value = untag_value(record.get("raw_value"))
        self.offset = record.get("value_offset")
        self.indirection_length = record.get("indirection_length")


class DorisDie:
    """DIE reconstructed lazily from Doris DIE and attribute rows."""

    def __init__(self, store: DorisStoreView, data: DorisDieData) -> None:
        self._store = store
        self._data = data
        self.tag = data.tag
        self.offset = data.die_offset
        self.has_children = data.has_children
        self.attributes = {name: DorisAttribute(record) for name, record in data.attributes.items()}
        self.cu = store.compilation_unit_by_offset(data.unit_offset)
        self.dwarfinfo = store.dwarf_info
        self.depth = data.depth

    def __getitem__(self, attribute_name: str) -> DorisAttribute:
        return self.attributes[attribute_name]

    def get_DIE_from_attribute(self, attribute_name: str) -> DorisDie | None:
        target_offset = self._store.attribute_target(self.offset, attribute_name)
        return self._store.die_by_offset(target_offset)

    def get_full_path(self) -> str:
        names: list[str] = []
        current: DorisDie | None = self
        while current is not None:
            attribute = current.attributes.get("DW_AT_name")
            if attribute is not None and attribute.value:
                names.append(_text(attribute.value))
            current = current.get_parent()
        return "::".join(reversed(names))

    def get_parent(self) -> DorisDie | None:
        parent_offset = self._data.parent_offset
        return self._store.die_by_offset(parent_offset)

    def iter_children(self) -> Iterable[DorisDie]:
        return self._store.children_for_die(self.offset)

    def is_null(self) -> bool:
        return self._data.is_null

    @property
    def parent_offset(self) -> int | None:
        """Return the source-bound parent offset without another query."""
        return self._data.parent_offset


class DorisDieData:
    """DIE identity plus the attributes hydrated for that DIE."""

    def __init__(
        self,
        *,
        unit_offset: int,
        die_offset: int,
        ordinal: int,
        tag: str | None,
        abbrev_code: int | None,
        has_children: bool,
        depth: int,
        parent_offset: int | None,
        is_null: bool,
        attributes: dict[str, dict[str, Any]],
    ) -> None:
        self.unit_offset = unit_offset
        self.die_offset = die_offset
        self.ordinal = ordinal
        self.tag = tag
        self.abbrev_code = abbrev_code
        self.has_children = has_children
        self.depth = depth
        self.parent_offset = parent_offset
        self.is_null = is_null
        self.attributes = attributes


class _EmptyLineProgram:
    """Explicit empty line-program view when no line rows exist."""

    header: dict[str, list[Any]] = {"file_entry": []}


class DorisDwarfInfo:
    """DwarfInfo protocol implemented by the Doris serving projection."""

    def __init__(self, store: DorisStoreView) -> None:
        self._store = store

    def iter_CUs(self) -> Iterable[DorisCompilationUnit]:
        return self._store.iter_dwarf_units()

    def get_DIE_from_refaddr(self, refaddr: int, cu: Any = None) -> DorisDie | None:
        del cu
        return self._store.die_by_offset(refaddr)

    def line_program_for_CU(self, CU: Any) -> StoreLineProgram | _EmptyLineProgram:  # noqa: N803
        program = self._store.line_program_for_unit(int(CU.cu_offset))
        return program if program is not None else _EmptyLineProgram()


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)

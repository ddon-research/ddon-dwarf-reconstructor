"""Technology-neutral debug-information contracts for the runtime hexagon.

The concrete pyelftools objects are owned by the ELF adapter. Core and
application signatures use these structural contracts instead of exposing
pyelftools classes to callers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

# These names intentionally mirror the pyelftools protocol surface so that
# adapters can satisfy the contracts without leaking the dependency inward.
# ruff: noqa: N802


class DwarfAttribute(Protocol):
    """Minimum attribute surface consumed by reconstruction policies."""

    value: Any
    form: str


class DwarfInfo(Protocol):
    """Debug-information source operations used by the core."""

    def iter_CUs(self) -> Any: ...

    def get_DIE_from_refaddr(self, refaddr: int, cu: Any = None) -> Any: ...

    def line_program_for_CU(self, CU: Any) -> Any:  # noqa: N803
        ...


class DwarfCompilationUnit(Protocol):
    """Compilation-unit data required by parsing and rendering policies."""

    cu_offset: int
    header: Mapping[str, Any]
    dwarfinfo: DwarfInfo

    def iter_DIEs(self) -> Any: ...

    def get_top_DIE(self) -> Any: ...

    def __getitem__(self, key: str) -> Any: ...


def compilation_unit_length(cu: DwarfCompilationUnit) -> int:
    """Read the normalized CU length at the DWARF boundary."""
    header = cu.header
    raw_length = (
        header.get("unit_length")
        if isinstance(header, Mapping)
        else getattr(header, "unit_length", None)
    )
    if not isinstance(raw_length, int):
        raise ValueError(f"Compilation unit 0x{cu.cu_offset:x} has no integer unit_length")
    return raw_length


def decode_dwarf_string(value: Any, default: str = "") -> str:
    """Decode a DWARF string attribute without allowing malformed bytes to escape."""
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class DwarfEntry(Protocol):
    """A debug-information entry as seen through the core port."""

    tag: Any
    offset: int
    attributes: Any
    cu: Any
    dwarfinfo: Any
    has_children: Any

    def __getitem__(self, attribute_name: str) -> Any: ...

    def get_DIE_from_attribute(self, attribute_name: str) -> Any: ...

    def get_full_path(self) -> str: ...

    def get_parent(self) -> Any: ...

    def iter_children(self) -> Any: ...

    def is_null(self) -> bool: ...

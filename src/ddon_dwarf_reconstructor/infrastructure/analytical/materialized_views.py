"""Small adapter protocol shared by JSONL and Parquet materialized views."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from ...domain.models.analytical_dwarf import QueryResult


class MaterializedStorePort(Protocol):
    """Operations required by generator-compatible materialized views.

    This protocol deliberately contains only the view/navigation surface. It
    does not make one physical projection a subtype of another.
    """

    manifest_path: Path
    dwarf_info: Any

    def dies_for_unit(self, unit_offset: int) -> Iterable[Any]: ...

    def iter_dwarf_units(self) -> Iterable[Any]: ...

    def compilation_unit_by_offset(self, unit_offset: int) -> Any: ...

    def die_by_offset(self, die_offset: int | None) -> Any | None: ...

    def children_for_die(self, die_offset: int) -> Iterable[Any]: ...

    def attribute_target(self, die_offset: int, attribute_name: str) -> int | None: ...

    def line_program_for_unit(self, unit_offset: int) -> Any | None: ...

    def child_tag_counts(self, die_offset: int) -> Any: ...


class MaterializedQueryPort(MaterializedStorePort, Protocol):
    """Materialized view operations required by query-backed cache adapters."""

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult: ...


__all__ = ["MaterializedQueryPort", "MaterializedStorePort"]

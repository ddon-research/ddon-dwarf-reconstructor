"""Read-only unit, line-program, and DwarfInfo views over a Doris store."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from ...core.dwarf import DwarfInfo
from ...domain.models.analytical_dwarf import MaterializedUnit
from .doris_batch_rows import hydration_rows
from .doris_models import DorisCompilationUnit
from .line_program import StoreLineProgram, build_line_program


class _StoreAccessHost(Protocol):
    dwarf_info: DwarfInfo
    _line_programs: Any
    _name_lookup_table: str
    _rows: Any
    _source_id: str
    _units: Any

    def _manifest_count(self, family: str) -> int: ...

    def _unit_from_record(self, record: dict[str, Any]) -> DorisCompilationUnit: ...

    def record_cache_hit(self) -> None: ...

    def record_cache_miss(self) -> None: ...


class DorisStoreAccessMixin:
    """Provide read-only views that are independent of DIE hydration."""

    def iter_compilation_units(self: _StoreAccessHost) -> Iterable[MaterializedUnit]:
        rows = hydration_rows(
            self, "unit", order_by=("unit_offset",), operation="iter_compilation_units"
        )
        for record in rows:
            header = record.get("header", {})
            yield MaterializedUnit(
                source_id=str(record.get("source_id", self._source_id)),
                unit_offset=int(record.get("unit_offset", 0)),
                unit_length=_optional_int(record.get("unit_length")),
                header=header if isinstance(header, dict) else {},
                unit_type=_optional_text(record.get("unit_type")),
                parser_status=_optional_text(record.get("parser_status")),
                details=record.get("details"),
            )

    def iter_dwarf_units(self: _StoreAccessHost) -> Iterable[DorisCompilationUnit]:
        for record in hydration_rows(
            self, "unit", order_by=("unit_offset",), operation="iter_dwarf_units"
        ):
            yield self._unit_from_record(record)

    def compilation_unit_by_offset(
        self: _StoreAccessHost, unit_offset: int
    ) -> DorisCompilationUnit:
        cached = self._units.get(unit_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        rows = tuple(
            hydration_rows(
                self,
                "unit",
                {"unit_offset": unit_offset},
                limit=1,
                operation="compilation_unit_by_offset",
            )
        )
        if not rows:
            raise KeyError(f"Compilation unit 0x{unit_offset:x} is not published")
        return self._unit_from_record(rows[0])

    def line_program_for_unit(self: _StoreAccessHost, unit_offset: int) -> StoreLineProgram | None:
        cached = self._line_programs.get(unit_offset)
        if unit_offset in self._line_programs:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        program = build_line_program(
            hydration_rows(
                self,
                "line",
                {"unit_offset": unit_offset},
                order_by=("ordinal",),
                operation="line_program_for_unit",
            )
        )
        self._line_programs[unit_offset] = program
        return program

    @property
    def unit_count(self: _StoreAccessHost) -> int:
        return self._manifest_count("unit")

    @property
    def die_count(self: _StoreAccessHost) -> int:
        return self._manifest_count("die")

    @property
    def definition_name_count(self: _StoreAccessHost) -> int:
        cached = vars(self).get("_definition_name_count_cache")
        if cached is None:
            rows = hydration_rows(
                self,
                "index",
                {"index_type": "definition"},
                columns=("name",),
                table_name=self._name_lookup_table,
                operation="definition_name_count",
            )
            cached = len({row.get("name") for row in rows if isinstance(row.get("name"), str)})
            vars(self)["_definition_name_count_cache"] = cached
        return cached

    def as_dwarf_info(self: _StoreAccessHost) -> DwarfInfo:
        return self.dwarf_info


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = ["DorisStoreAccessMixin"]

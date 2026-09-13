"""DIE and compilation-unit materialization for the Doris store façade."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from ...core.dwarf import DwarfInfo
from ...domain.models.analytical_dwarf import MaterializationManifest
from .doris_batch_rows import hydration_rows
from .doris_hydration import (
    _DorisHydrationStore,
    attribute_projection_columns,
    attributes_by_die,
)
from .doris_models import DorisCompilationUnit, DorisDie, DorisDieData, DorisStoreView
from .doris_reference_hydration import register_reference_candidate
from .doris_store_helpers import optional_int, optional_text


class DorisStoreHydrationPort(_DorisHydrationStore, DorisStoreView, Protocol):
    """State and operations required by the store's record materializer."""

    manifest: MaterializationManifest
    dwarf_info: DwarfInfo

    def record_cache_hit(self) -> None: ...

    def record_cache_miss(self) -> None: ...

    def _cached_die(
        self, unit_offset: int, die_offset: int
    ) -> tuple[DorisDie | None, int | None]: ...

    def _attribute_rows_for_die(
        self,
        unit_offset: int,
        die_offset: int,
        attributes: Iterable[dict[str, Any]] | None,
    ) -> Iterable[dict[str, Any]]: ...

    def _construct_die(
        self, record: Mapping[str, Any], attribute_rows: Iterable[dict[str, Any]]
    ) -> DorisDie: ...

    def _cache_die(self, die: DorisDie, known_unit: int | None) -> None: ...


class DorisStoreHydrationMixin:
    """Materialize typed DIE views while preserving bounded store caches."""

    def _unit_from_record(
        self: DorisStoreHydrationPort,
        record: dict[str, Any],
    ) -> DorisCompilationUnit:
        unit_offset = int(record.get("unit_offset", 0))
        cached = self._units.get(unit_offset)
        if cached is not None:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        unit = DorisCompilationUnit(self, record)
        self._units[unit_offset] = unit
        return unit

    def _die_from_index_record(
        self: DorisStoreHydrationPort,
        record: Mapping[str, object],
    ) -> DorisDie | None:
        unit_offset = optional_int(record.get("unit_offset"))
        die_offset = optional_int(record.get("die_offset"))
        if unit_offset is None or die_offset is None:
            return None
        exact = getattr(self, "_dies_by_key", None)
        if exact is not None:
            cached = exact.get((unit_offset, die_offset))
            if cached is not None:
                return cached
        cached = self._dies.get(die_offset)
        if cached is not None and self._die_unit_offsets.get(die_offset) == unit_offset:
            return cached
        rows = tuple(
            hydration_rows(
                self,
                "die",
                {"unit_offset": unit_offset, "die_offset": die_offset},
                limit=1,
                operation="hydrate_index_die",
            )
        )
        return self._die_from_record(rows[0]) if rows else None

    def _die_from_record(
        self: DorisStoreHydrationPort,
        record: Mapping[str, Any],
        attributes: Iterable[dict[str, Any]] | None = None,
    ) -> DorisDie:
        die_offset = int(record.get("die_offset", 0))
        unit_offset = int(record.get("unit_offset", 0))
        cached, known_unit = self._cached_die(unit_offset, die_offset)
        if cached is not None and known_unit == unit_offset:
            self.record_cache_hit()
            return cached
        self.record_cache_miss()
        if known_unit is None:
            self._die_unit_offsets[die_offset] = unit_offset
        attribute_rows = self._attribute_rows_for_die(unit_offset, die_offset, attributes)
        die = self._construct_die(record, attribute_rows)
        self._cache_die(die, known_unit)
        register_reference_candidate(self, die)
        return die

    def _cached_die(
        self: DorisStoreHydrationPort, unit_offset: int, die_offset: int
    ) -> tuple[DorisDie | None, int | None]:
        exact = getattr(self, "_dies_by_key", None)
        if exact is not None:
            cached = exact.get((unit_offset, die_offset))
            if cached is not None:
                return cached, unit_offset
        known_unit = self._die_unit_offsets.get(die_offset)
        return self._dies.get(die_offset), known_unit

    def _attribute_rows_for_die(
        self: DorisStoreHydrationPort,
        unit_offset: int,
        die_offset: int,
        attributes: Iterable[dict[str, Any]] | None,
    ) -> Iterable[dict[str, Any]]:
        if attributes is not None:
            return tuple(attributes)
        return hydration_rows(
            self,
            "attribute",
            {"unit_offset": unit_offset, "die_offset": die_offset},
            columns=attribute_projection_columns(self),
            order_by=("ordinal",),
            operation="hydrate_die_attributes",
        )

    def _construct_die(
        self: DorisStoreHydrationPort,
        record: Mapping[str, Any],
        attribute_rows: Iterable[dict[str, Any]],
    ) -> DorisDie:
        unit_offset = int(record.get("unit_offset", 0))
        die_offset = int(record.get("die_offset", 0))
        data = DorisDieData(
            unit_offset=unit_offset,
            die_offset=die_offset,
            ordinal=int(record.get("ordinal", 0)),
            tag=optional_text(record.get("tag")),
            abbrev_code=optional_int(record.get("abbrev_code")),
            has_children=bool(record.get("has_children", False)),
            depth=int(record.get("depth", 0)),
            parent_offset=optional_int(record.get("parent_offset")),
            is_null=bool(record.get("is_null", False)),
            attributes={str(row.get("name", "")): row for row in attribute_rows},
        )
        return DorisDie(self, data)

    def _cache_die(self: DorisStoreHydrationPort, die: DorisDie, known_unit: int | None) -> None:
        unit_offset = die.cu.cu_offset
        die_offset = die.offset
        exact = getattr(self, "_dies_by_key", None)
        if exact is not None:
            exact[(unit_offset, die_offset)] = die
        if known_unit is None or known_unit == unit_offset:
            self._dies[die_offset] = die

    def _attributes_by_die(
        self: DorisStoreHydrationPort,
        unit_offset: int | None,
        records: Iterable[Mapping[str, Any]],
    ) -> dict[int, tuple[dict[str, Any], ...]]:
        return attributes_by_die(self, unit_offset, records)

    def _manifest_count(self: DorisStoreHydrationPort, family: str) -> int:
        return self.manifest.counts.get(family, 0)

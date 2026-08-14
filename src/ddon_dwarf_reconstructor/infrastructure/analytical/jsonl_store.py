"""Validated JSONL query adapter and generator-compatible materialized facade."""

# The names intentionally mirror the pyelftools protocol at this adapter boundary.
# ruff: noqa: N802

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter
from typing import Any

from ...core.dwarf import DwarfInfo
from ...domain.models.analytical_dwarf import (
    MaterializationManifest,
    MaterializedUnit,
    QueryResult,
    QueryStatus,
)
from ...domain.ports.cache import SymbolCachePort
from ...domain.services.definition_selection import NestedTypeCounts
from ...domain.services.search_result import SearchResult, search_status_for_query
from ..artifacts import SourceIdentityCatalog
from .bounded_query_cache import BoundedQueryCache
from .json_codec import untag_value
from .jsonl_models import DieData
from .jsonl_views import (
    StoreCompilationUnit,
    StoreDie,
    StoreDwarfInfo,
    _MaterializedCache,
)
from .line_program import StoreLineProgram, build_line_program
from .manifest import (
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
    validate_manifest_files,
    validate_schema_version,
)
from .materialized_selection import (
    DEFINITION_QUERY_LIMIT as _DEFINITION_QUERY_LIMIT,
)
from .materialized_selection import (
    definition_candidate as _definition_candidate,
)
from .materialized_selection import (
    definition_matches as _definition_matches,
)
from .materialized_selection import (
    definition_sort_key as _definition_sort_key,
)
from .materialized_selection import (
    query_status as _query_status,
)
from .materialized_selection import (
    result as _result,
)
from .store_selection import load_selection_cache, prefer_cached_definition


class JsonlDwarfStore:
    """Load a validated JSONL audit store into bounded offset/name indexes."""

    def __init__(
        self,
        manifest_path: Path,
        manifest: MaterializationManifest,
        *,
        selection_cache: SymbolCachePort | None = None,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.manifest = manifest
        self.root = self.manifest_path.parent
        self._selection_cache = selection_cache
        self._units: dict[int, StoreCompilationUnit] = {}
        self._unit_records: dict[int, dict[str, Any]] = {}
        self._die_data: dict[int, DieData] = {}
        self._dies: dict[int, StoreDie] = {}
        self._dies_by_unit: dict[int, list[StoreDie]] = defaultdict(list)
        self._children: dict[int, list[StoreDie]] = defaultdict(list)
        self._attributes: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._attribute_targets: dict[tuple[int, str], int] = {}
        self._references: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self._line_records: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self._derived_definitions: dict[str, list[int]] = defaultdict(list)
        self._derived_methods: dict[int, list[int]] = defaultdict(list)
        self._definitions: dict[str, list[StoreDie]] = defaultdict(list)
        self._methods: dict[int, StoreDie] = {}
        self._definition_query_cache = BoundedQueryCache()
        self.dwarf_info = StoreDwarfInfo(self)
        self._load_records()
        self._build_views()
        self.persistent_cache = _MaterializedCache(self)

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        *,
        verify_source: bool = True,
        source_path: Path | None = None,
        allow_incomplete: bool = False,
        verify_artifacts: bool = False,
        selection_cache_path: Path | None = None,
        selection_source_fingerprint: dict[str, int | str] | None = None,
    ) -> JsonlDwarfStore:
        manifest_path = manifest_path.resolve()
        manifest = load_manifest(manifest_path)
        validate_schema_version(manifest, allow_incomplete=allow_incomplete)
        if has_parser_diagnostics(manifest) and not allow_incomplete:
            raise ValueError(f"Analytical store has partial DWARF parsing: {manifest_path}")
        if has_unapplied_source_recovery(manifest) and not allow_incomplete:
            raise ValueError(f"Analytical store lacks source-bound DWARF recovery: {manifest_path}")
        if manifest.status != "complete" and not allow_incomplete:
            raise ValueError(f"Analytical store is not complete: {manifest_path}")
        validate_manifest_files(manifest_path, manifest, verify_hashes=verify_artifacts)
        verify_source and _verify_source_binding(manifest, source_path)
        selection_cache = load_selection_cache(
            manifest,
            selection_cache_path,
            source_fingerprint=selection_source_fingerprint,
        )
        return cls(manifest_path, manifest, selection_cache=selection_cache)

    def iter_compilation_units(self) -> Iterable[MaterializedUnit]:
        for offset, record in sorted(self._unit_records.items()):
            header = untag_value(record.get("header", {}))
            yield MaterializedUnit(
                source_id=str(record.get("source_id", self.manifest.source_identity.sha256)),
                unit_offset=offset,
                unit_length=_optional_int(record.get("unit_length")),
                header=header if isinstance(header, dict) else {},
                unit_type=record.get("unit_type")
                if isinstance(record.get("unit_type"), str)
                else None,
            )

    def iter_dwarf_units(self) -> Iterable[StoreCompilationUnit]:
        return self._units.values()

    def compilation_unit_by_offset(self, unit_offset: int) -> StoreCompilationUnit:
        unit = self._units.get(unit_offset)
        if unit is None:
            raise KeyError(f"Compilation unit 0x{unit_offset:x} is not materialized")
        return unit

    def die_by_offset(self, die_offset: int | None) -> StoreDie | None:
        return self._dies.get(die_offset) if die_offset is not None else None

    def dies_for_unit(self, unit_offset: int) -> Iterable[StoreDie]:
        return iter(self._dies_by_unit.get(unit_offset, ()))

    def children_for_die(self, die_offset: int) -> Iterable[StoreDie]:
        return iter(self._children.get(die_offset, ()))

    def attribute_target(self, die_offset: int, attribute_name: str) -> int | None:
        return self._attribute_targets.get((die_offset, attribute_name))

    def line_program_for_unit(self, unit_offset: int) -> StoreLineProgram | None:
        """Return a reconstructed line program for one CU."""
        return build_line_program(self._line_records.get(unit_offset, ()))

    def child_tag_counts(self, die_offset: int) -> NestedTypeCounts:
        counts = {"DW_TAG_enumeration_type": 0, "DW_TAG_structure_type": 0, "DW_TAG_union_type": 0}
        for child in self._children.get(die_offset, ()):
            if not child.is_null() and child.tag in counts:
                counts[child.tag] += 1
        return NestedTypeCounts(
            enums=counts["DW_TAG_enumeration_type"],
            structs=counts["DW_TAG_structure_type"],
            unions=counts["DW_TAG_union_type"],
        )

    @property
    def unit_count(self) -> int:
        """Return the number of source compilation units in the store."""
        return len(self._units)

    @property
    def die_count(self) -> int:
        """Return the number of materialized DIE records, including nulls."""
        return len(self._dies)

    @property
    def definition_name_count(self) -> int:
        """Return the number of distinct derived definition names."""
        return len(self._definitions)

    def get_compilation_unit(self, unit_offset: int) -> QueryResult:
        unit = self._units.get(unit_offset)
        return _result(unit, self.manifest_path, self.manifest.status)

    def get_die(self, die_offset: int) -> QueryResult:
        return _result(self._dies.get(die_offset), self.manifest_path, self.manifest.status)

    def find_definitions(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        cache = self._definition_query_cache
        cache_key = (name, qualified_name, tags)
        cached_result = cache.lookup(cache_key)
        if cached_result is not None:
            return cached_result

        candidates = tuple(
            die
            for die in self._definitions.get(name, ())
            if _definition_matches(die, qualified_name, tags)
        )
        truncated = len(candidates) > _DEFINITION_QUERY_LIMIT
        candidates = candidates[:_DEFINITION_QUERY_LIMIT]
        items = prefer_cached_definition(name, candidates, self._selection_cache)
        status = _query_status(bool(items), self.manifest.status, truncated=truncated)
        diagnostics = ("definition query reached its safety bound",) if truncated else ()
        result = QueryResult(
            status,
            items,
            (str(self.manifest_path),),
            diagnostics,
            truncated,
        )
        cache[cache_key] = result
        return result

    def find_primary_definition(
        self,
        name: str,
        *,
        qualified_name: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> QueryResult:
        result = self.find_definitions(name, qualified_name=qualified_name, tags=tags)
        return QueryResult(
            result.status,
            result.items[:1],
            result.provenance,
            result.diagnostics,
            result.truncated,
        )

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        item = self._methods.get(declaration_offset)
        return _result(item, self.manifest_path, self.manifest.status)

    def children(self, die_offset: int) -> QueryResult:
        items = tuple(self._children.get(die_offset, ()))
        status = _query_status(bool(items), self.manifest.status)
        return QueryResult(status, items, (str(self.manifest_path),))

    def parent(self, die_offset: int) -> QueryResult:
        die = self._dies.get(die_offset)
        parent = die.get_parent() if die is not None else None
        return _result(parent, self.manifest_path, self.manifest.status)

    def references(self, die_offset: int) -> QueryResult:
        items = tuple(self._references.get(die_offset, ()))
        status = _query_status(bool(items), self.manifest.status)
        return QueryResult(status, items, (str(self.manifest_path),))

    def _load_records(self) -> None:
        records_path = self.root / self.manifest.files["records"]
        with records_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Invalid JSONL at {records_path}:{line_number}") from error
                if not isinstance(record, dict):
                    raise ValueError(f"JSONL record is not an object at line {line_number}")
                self._accept_record(record)

    def _accept_record(self, record: dict[str, Any]) -> None:
        kind = record.get("record_type")
        if not isinstance(kind, str):
            return
        handlers = {
            "unit": self._accept_unit,
            "die": self._accept_die,
            "attribute": self._accept_attribute,
            "reference": self._accept_reference,
            "index": self._accept_index,
            "line": self._accept_line,
        }
        handler = handlers.get(kind)
        if handler is not None:
            handler(record)

    def _accept_unit(self, record: dict[str, Any]) -> None:
        unit_offset = int(record.get("unit_offset", 0))
        self._unit_records[unit_offset] = record

    def _accept_die(self, record: dict[str, Any]) -> None:
        die_offset = int(record.get("die_offset", 0))
        self._die_data[die_offset] = DieData(
            unit_offset=int(record.get("unit_offset", 0)),
            die_offset=die_offset,
            ordinal=int(record.get("ordinal", 0)),
            tag=record.get("tag"),
            abbrev_code=record.get("abbrev_code"),
            has_children=bool(record.get("has_children", False)),
            depth=int(record.get("depth", 0)),
            parent_offset=record.get("parent_offset"),
            is_null=bool(record.get("is_null", False)),
            attributes={},
        )

    def _accept_attribute(self, record: dict[str, Any]) -> None:
        die_offset = int(record.get("die_offset", 0))
        self._attributes[die_offset][str(record.get("name", ""))] = record

    def _accept_reference(self, record: dict[str, Any]) -> None:
        die_offset = int(record.get("die_offset", 0))
        self._references[die_offset].append(record)
        if record.get("relation") != "attribute_reference":
            return
        target = record.get("target_offset")
        if isinstance(target, int):
            attribute_name = str(record.get("attribute_name", ""))
            self._attribute_targets[(die_offset, attribute_name)] = target

    def _accept_index(self, record: dict[str, Any]) -> None:
        index_type = record.get("index_type")
        if index_type == "definition" and isinstance(record.get("name"), str):
            self._accept_definition_index(record)
        elif index_type == "method_implementation":
            self._accept_method_index(record)

    def _accept_line(self, record: dict[str, Any]) -> None:
        unit_offset = record.get("unit_offset")
        if isinstance(unit_offset, int) and not isinstance(unit_offset, bool):
            self._line_records[unit_offset].append(record)

    def _accept_definition_index(self, record: dict[str, Any]) -> None:
        self._derived_definitions[record["name"]].append(int(record.get("die_offset", 0)))

    def _accept_method_index(self, record: dict[str, Any]) -> None:
        if record.get("resolution_status") != QueryStatus.COMPLETE.value or not isinstance(
            record.get("target_offset"), int
        ):
            return
        self._derived_methods[record["target_offset"]].append(int(record.get("die_offset", 0)))

    def _build_views(self) -> None:
        self._units = {
            offset: StoreCompilationUnit(self, record)
            for offset, record in sorted(self._unit_records.items())
        }
        for die_offset, data in sorted(self._die_data.items(), key=lambda item: item[1].ordinal):
            data.attributes = self._attributes.get(die_offset, {})
            die = StoreDie(self, data)
            self._dies[die_offset] = die
            self._dies_by_unit[data.unit_offset].append(die)
        for die in self._dies.values():
            if die.cu.cu_offset not in self._units:
                raise ValueError(
                    f"DIE 0x{die.offset:x} references missing CU 0x{die.cu.cu_offset:x}"
                )
            parent = die.get_parent()
            if parent is not None and not die.is_null():
                self._children[parent.offset].append(die)
        for unit_offset, _unit in self._units.items():
            if unit_offset not in self._dies_by_unit:
                raise ValueError(f"CU 0x{unit_offset:x} has no DIE records")
        self._build_indexes()

    def _build_indexes(self) -> None:
        if self._derived_definitions:
            self._build_derived_definitions()
        else:
            self._build_legacy_definitions()
        if self._derived_methods:
            self._build_derived_methods()
        else:
            self._build_legacy_methods()
        for name, values in self._definitions.items():
            self._definitions[name] = sorted(values, key=_definition_sort_key)

    def _build_derived_definitions(self) -> None:
        for name, offsets in self._derived_definitions.items():
            self._definitions[name].extend(
                self._dies[offset] for offset in offsets if offset in self._dies
            )

    def _build_legacy_definitions(self) -> None:
        for die in self._dies.values():
            if die.is_null():
                continue
            name = die.attributes.get("DW_AT_name")
            if name is not None:
                self._definitions[_text(name.value)].append(die)

    def _build_derived_methods(self) -> None:
        for declaration_offset, implementation_offsets in self._derived_methods.items():
            for implementation_offset in implementation_offsets:
                implementation = self._dies.get(implementation_offset)
                if implementation is not None:
                    self._methods[declaration_offset] = implementation

    def _build_legacy_methods(self) -> None:
        for die in self._dies.values():
            specification = die.get_DIE_from_attribute("DW_AT_specification")
            if specification is not None and die.tag == "DW_TAG_subprogram":
                self._methods[specification.offset] = die

    def as_dwarf_info(self) -> DwarfInfo:
        return self.dwarf_info


class MaterializedDwarfIndex:
    """Generator lookup adapter backed by precomputed analytical store indexes."""

    persistent_cache: SymbolCachePort

    def __init__(self, store: JsonlDwarfStore) -> None:
        self.store = store
        self.persistent_cache = store.persistent_cache

    def find_symbol_offset(self, symbol_name: str) -> int | None:
        result = self.store.find_primary_definition(symbol_name)
        if result.status is not QueryStatus.COMPLETE:
            return None
        item = result.items[0] if result.items else None
        return item.offset if isinstance(item, StoreDie) else None

    def find_definition_tag(self, symbol_name: str) -> QueryResult:
        """Return the tag from a complete materialized definition result."""
        result = self.store.find_primary_definition(symbol_name)
        item = result.items[0] if result.items else None
        tag = getattr(item, "tag", None)
        if result.status is QueryStatus.COMPLETE and isinstance(tag, str):
            return QueryResult(QueryStatus.COMPLETE, (tag,), result.provenance)
        return QueryResult(
            result.status,
            diagnostics=result.diagnostics,
            provenance=result.provenance,
            truncated=result.truncated,
        )

    def targeted_symbol_search(
        self, symbol_name: str, timeout: float | None = None
    ) -> SearchResult:
        del timeout
        started = perf_counter()
        result = self.store.find_primary_definition(symbol_name)
        candidates = [self._candidate(symbol_name, die) for die in result.items]
        candidate = candidates[0] if candidates else None
        return SearchResult(
            status=search_status_for_query(result.status),
            candidate=candidate,
            elapsed_seconds=perf_counter() - started,
            cus_searched=self.store.unit_count,
            diagnostics=result.diagnostics,
        )

    def get_die_by_offset(self, offset: int) -> StoreDie | None:
        return self.store.die_by_offset(offset)

    def save_cache(self) -> None:
        return

    @staticmethod
    def _candidate(symbol_name: str, die: StoreDie):
        return _definition_candidate(symbol_name, die)


def _verify_source_binding(
    manifest: MaterializationManifest,
    source_path: Path | None = None,
) -> None:
    source = (source_path or Path(manifest.source_path)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Materialization source is unavailable: {source}")
    identity = SourceIdentityCatalog().identify(source)
    if identity.sha256 != manifest.source_identity.sha256:
        raise ValueError(f"Materialization source hash mismatch: {source}")


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _is_complete_definition(die: StoreDie) -> bool:
    return "DW_AT_declaration" not in die.attributes


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""

"""Bounded Doris projection for implementation-validation context rows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from ...domain.models.analytical_dwarf import (
    MethodContextBatch,
    MethodContextRequest,
    QueryResult,
    QueryStatus,
)
from .doris import DorisConfig
from .doris_rows import restore_row
from .doris_store_helpers import bounded_query_diagnostic

_DIE_COLUMNS = (
    "unit_offset",
    "die_offset",
    "ordinal",
    "tag",
    "abbrev_code",
    "has_children",
    "depth",
    "parent_offset",
    "is_null",
)
_FRAME_COLUMNS = (
    "record_type",
    "section_name",
    "record_offset",
    "record_length",
    "frame_kind",
    "initial_address",
    "address_range",
    "parser_status",
    "details_json",
)
_ATTRIBUTE_COLUMNS = (
    "unit_offset",
    "die_offset",
    "ordinal",
    "record_type",
    "name",
    "form",
    "value_offset",
    "indirection_length",
    "decoded_value_kind",
    "decoded_value_bool",
    "decoded_value_int",
    "decoded_value_uint",
    "decoded_value_float",
    "decoded_value_binary",
    "decoded_value_text",
    "decoded_value_json",
    "decoded_value_path",
    "decoded_value_sha256",
    "decoded_value_size",
)
_CONTEXT_BATCH_SIZE = 512


class DorisContextStore(Protocol):
    """Small store surface required by the validation projection."""

    manifest_path: Path
    manifest: Any
    _config: DorisConfig
    _queries: Any

    def _rows(
        self,
        family: str,
        filters: Mapping[str, object] | None = None,
        *,
        columns: Sequence[str] = (),
        order_by: Sequence[str] = (),
        limit: int | None = None,
        table_name: str | None = None,
        operation: str = "family_rows",
    ) -> tuple[dict[str, Any], ...]: ...


def batched_requests(
    requests: Sequence[MethodContextRequest], size: int = _CONTEXT_BATCH_SIZE
) -> tuple[tuple[MethodContextRequest, ...], ...]:
    """Partition context requests into deterministic bounded batches."""
    if size < 1:
        raise ValueError("context batch size must be positive")
    ordered = tuple(sorted(requests, key=lambda item: item.key))
    return tuple(tuple(ordered[start : start + size]) for start in range(0, len(ordered), size))


def query_method_context_batch(
    store: DorisContextStore,
    requests: Sequence[MethodContextRequest],
) -> QueryResult:
    """Read one bounded context projection from Doris family tables."""
    ordered = tuple(sorted(requests, key=lambda item: item.key))
    if not ordered:
        return QueryResult(QueryStatus.COMPLETE, (MethodContextBatch(),), _provenance(store))
    try:
        method_offsets = _unique_offsets(item.die_offsets for item in ordered)
        method_rows = _die_rows(store, {"die_offset": method_offsets}, "validation_method_dies")
        parameter_rows = _die_rows(
            store,
            {
                "parent_offset": method_offsets,
                "tag": ("DW_TAG_formal_parameter",),
            },
            "validation_parameter_dies",
        )
        parameter_offsets = _row_offsets(parameter_rows)
        context_offsets = _unique_offsets((method_offsets, parameter_offsets))
        references = store._rows(
            "reference",
            {"die_offset": context_offsets, "relation": "attribute_reference"},
            order_by=("unit_offset", "die_offset", "attribute_name"),
            operation="validation_references",
        )
        target_offsets = _unique_offsets((_reference_targets(references),))
        target_rows = _die_rows(store, {"die_offset": target_offsets}, "validation_target_dies")
        all_die_rows = _unique_rows(
            (*method_rows, *parameter_rows, *target_rows),
            ("unit_offset", "die_offset"),
        )
        attribute_offsets = _unique_offsets((_row_offsets(all_die_rows),))
        attributes = store._rows(
            "attribute",
            {"die_offset": attribute_offsets},
            columns=_ATTRIBUTE_COLUMNS,
            order_by=("unit_offset", "die_offset", "ordinal"),
            operation="validation_attributes",
        )
        locations = store._rows(
            "location",
            {"die_offset": context_offsets},
            order_by=("unit_offset", "die_offset", "ordinal", "record_offset"),
            operation="validation_locations",
        )
        frames = _frame_rows(store, ordered)
        batch = MethodContextBatch(
            die_rows=all_die_rows,
            attribute_rows=tuple(attributes),
            reference_rows=tuple(references),
            location_rows=tuple(locations),
            frame_rows=frames,
            status=(
                QueryStatus.COMPLETE if store.manifest.status == "complete" else QueryStatus.PARTIAL
            ),
        )
        return QueryResult(batch.status, (batch,), _provenance(store))
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        return QueryResult(
            QueryStatus.UNAVAILABLE,
            provenance=_provenance(store),
            diagnostics=(
                bounded_query_diagnostic(error, prefix="Doris implementation context unavailable"),
            ),
        )


def merge_context_batches(
    batches: Sequence[MethodContextBatch],
) -> MethodContextBatch:
    """Merge bounded batches without duplicating rows at frame-window edges."""
    return MethodContextBatch(
        die_rows=_merged_rows(batches, "die_rows", ("unit_offset", "die_offset")),
        attribute_rows=_merged_rows(
            batches, "attribute_rows", ("unit_offset", "die_offset", "ordinal")
        ),
        reference_rows=_merged_rows(
            batches, "reference_rows", ("unit_offset", "die_offset", "attribute_name", "relation")
        ),
        location_rows=_merged_rows(
            batches, "location_rows", ("unit_offset", "die_offset", "ordinal", "record_offset")
        ),
        frame_rows=_merged_rows(batches, "frame_rows", ("section_name", "record_offset")),
        status=_batch_status(batches),
        diagnostics=_merged_diagnostics(batches),
    )


class DorisBatchContextQuery:
    """Read-only in-memory view over one or more validated Doris batches."""

    def __init__(
        self,
        batch: MethodContextBatch,
        manifest_path: Path,
    ) -> None:
        self._status = batch.status
        self._diagnostics = batch.diagnostics
        self._provenance = (str(manifest_path),)
        self._dies = _build_dies(batch)
        self._locations = _group_rows(batch.location_rows, "die_offset")
        self._frames = batch.frame_rows

    def get_die(self, die_offset: int) -> QueryResult:
        die = self._dies.get(die_offset)
        return self._result((die,) if die is not None else ())

    def find_locations(self, die_offset: int, *, attribute_name: str | None = None) -> QueryResult:
        rows = self._locations.get(die_offset, ())
        if attribute_name is not None:
            rows = tuple(row for row in rows if row.get("attribute_name") == attribute_name)
        return self._result(rows)

    def find_frames(
        self, *, start_address: int | None = None, end_address: int | None = None
    ) -> QueryResult:
        rows = tuple(
            row for row in self._frames if _frame_overlaps(row, start_address, end_address)
        )
        return self._result(rows)

    def _result(self, items: Sequence[Any]) -> QueryResult:
        return QueryResult(
            self._status,
            tuple(items),
            self._provenance,
            self._diagnostics,
        )


class _BatchAttribute:
    def __init__(self, row: Mapping[str, Any]) -> None:
        self.form = str(row.get("form", ""))
        self.value = row.get("decoded_value")


class _BatchDie:
    def __init__(self, row: Mapping[str, Any], attributes: Mapping[str, _BatchAttribute]) -> None:
        self.offset = _as_int(row.get("die_offset")) or 0
        self.tag = row.get("tag")
        self.attributes = dict(attributes)
        self._references: dict[str, int] = {}
        self._children: tuple[_BatchDie, ...] = ()
        self._all_dies: dict[int, _BatchDie] = {}

    def get_DIE_from_attribute(self, attribute_name: str) -> _BatchDie | None:  # noqa: N802
        target = self._references.get(attribute_name)
        return self._all_dies.get(target) if target is not None else None

    def iter_children(self) -> tuple[_BatchDie, ...]:
        return self._children


def _build_dies(batch: MethodContextBatch) -> dict[int, _BatchDie]:
    dies = _dies_by_offset(batch.die_rows, _attributes_by_die(batch.attribute_rows))
    _attach_all_dies(dies)
    _attach_formal_parameters(dies, batch.die_rows)
    _attach_references(dies, batch.reference_rows)
    return dies


def _attributes_by_die(
    rows: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, _BatchAttribute]]:
    attributes: dict[int, dict[str, _BatchAttribute]] = defaultdict(dict)
    for row in rows:
        die_offset = _as_int(row.get("die_offset"))
        name = row.get("name")
        if die_offset is not None and isinstance(name, str):
            attributes[die_offset][name] = _BatchAttribute(row)

    return attributes


def _dies_by_offset(
    rows: Sequence[Mapping[str, Any]],
    attributes: Mapping[int, Mapping[str, _BatchAttribute]],
) -> dict[int, _BatchDie]:
    dies = {
        offset: _BatchDie(row, attributes.get(offset, {}))
        for row in rows
        if (offset := _as_int(row.get("die_offset"))) is not None
    }

    return dies


def _attach_all_dies(dies: dict[int, _BatchDie]) -> None:
    for die in dies.values():
        die._all_dies = dies


def _attach_formal_parameters(
    dies: Mapping[int, _BatchDie], rows: Sequence[Mapping[str, Any]]
) -> None:
    children: dict[int, list[_BatchDie]] = defaultdict(list)
    for row in rows:
        parent = _as_int(row.get("parent_offset"))
        child_offset = _as_int(row.get("die_offset"))
        child = dies.get(child_offset) if child_offset is not None else None
        if parent is not None and child is not None and row.get("tag") == "DW_TAG_formal_parameter":
            children[parent].append(child)
    for parent, values in children.items():
        if parent in dies:
            dies[parent]._children = tuple(sorted(values, key=lambda item: item.offset))


def _attach_references(dies: Mapping[int, _BatchDie], rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        source_offset = _as_int(row.get("die_offset"))
        source = dies.get(source_offset) if source_offset is not None else None
        name = row.get("attribute_name")
        target = _as_int(row.get("target_offset"))
        if source is not None and isinstance(name, str) and target is not None:
            source._references[name] = target


def _merged_rows(
    batches: Sequence[MethodContextBatch],
    field: str,
    keys: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    return _unique_rows(
        (row for batch in batches for row in getattr(batch, field)),
        keys,
    )


def _merged_diagnostics(batches: Sequence[MethodContextBatch]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for batch in batches for item in batch.diagnostics))


def _die_rows(
    store: DorisContextStore,
    filters: Mapping[str, object],
    operation: str,
) -> tuple[dict[str, Any], ...]:
    return store._rows(
        "die",
        filters,
        columns=_DIE_COLUMNS,
        order_by=("unit_offset", "ordinal"),
        table_name=store._config.die_lookup_table,
        operation=operation,
    )


def _frame_rows(
    store: DorisContextStore,
    requests: Sequence[MethodContextRequest],
) -> tuple[dict[str, Any], ...]:
    ranges = tuple(
        (item.start_address, item.end_address)
        for item in requests
        if item.start_address is not None and item.end_address is not None
    )
    if not ranges:
        return ()
    start = min(item[0] for item in ranges)
    end = max(item[1] for item in ranges)
    return tuple(
        restore_row(dict(row))
        for row in store._queries.frame_rows_overlapping(
            start,
            end,
            columns=_FRAME_COLUMNS,
            order_by=("section_name", "record_offset"),
        )
    )


def _unique_offsets(groups: Iterable[Iterable[int]]) -> tuple[int, ...]:
    return tuple(sorted({offset for group in groups for offset in group if offset >= 0}))


def _row_offsets(rows: Sequence[Mapping[str, Any]]) -> tuple[int, ...]:
    return tuple(
        sorted({offset for row in rows if (offset := _as_int(row.get("die_offset"))) is not None})
    )


def _reference_targets(rows: Sequence[Mapping[str, Any]]) -> tuple[int, ...]:
    return tuple(
        sorted(
            {target for row in rows if (target := _as_int(row.get("target_offset"))) is not None}
        )
    )


def _unique_rows(
    rows: Sequence[Mapping[str, Any]] | Any,
    keys: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    values: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        values.setdefault(tuple(row.get(key) for key in keys), dict(row))
    return tuple(values[key] for key in sorted(values, key=str))


def _group_rows(rows: Sequence[dict[str, Any]], key: str) -> dict[int, tuple[dict[str, Any], ...]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _as_int(row.get(key))
        if value is not None:
            grouped[value].append(row)
    return {offset: tuple(values) for offset, values in grouped.items()}


def _batch_status(batches: Sequence[MethodContextBatch]) -> QueryStatus:
    if any(batch.status is QueryStatus.UNAVAILABLE for batch in batches):
        return QueryStatus.UNAVAILABLE
    if any(batch.status is QueryStatus.PARTIAL for batch in batches):
        return QueryStatus.PARTIAL
    return QueryStatus.COMPLETE


def _frame_overlaps(row: Mapping[str, Any], start: int | None, end: int | None) -> bool:
    if start is None or end is None:
        return True
    initial = _as_int(row.get("initial_address"))
    span = _as_int(row.get("address_range"))
    return initial is not None and span is not None and initial < end and initial + span > start


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, Decimal)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _provenance(store: DorisContextStore) -> tuple[str, ...]:
    return (str(store.manifest_path),)


__all__ = [
    "DorisBatchContextQuery",
    "batched_requests",
    "merge_context_batches",
    "query_method_context_batch",
]

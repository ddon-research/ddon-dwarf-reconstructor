"""Analytical-store context for source-bound implementation validation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.models.analytical_dwarf import (
    MethodContextBatch,
    MethodContextRequest,
    QueryResult,
)
from ..domain.models.implementation_validation import (
    AnalyticalModelEvidence,
    EvidenceStatus,
    ValidationStatus,
)
from .analytical.doris import DorisConfig
from .analytical.doris_method_context import (
    DorisBatchContextQuery,
    batched_requests,
    merge_context_batches,
)
from .analytical.doris_serving_profile import DorisServingProfile
from .analytical.doris_store import DorisDwarfStore


@dataclass(slots=True)
class DorisImplementationEvidenceModel:
    """Small read-only query façade for method validation.

    The complete materialization manifest is only the publication identity and
    source-binding anchor. All method DIE, location, and CFI rows are queried
    from the validated Doris serving projection; this façade intentionally has
    no file-backed row reader.
    """

    _store: DorisDwarfStore
    identity: AnalyticalModelEvidence
    _batch_query: DorisBatchContextQuery | None = None

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        source: Path,
        *,
        config: DorisConfig | None = None,
    ) -> DorisImplementationEvidenceModel:
        """Open the complete source-bound Doris publication for validation."""
        config = config or DorisConfig.from_environment()
        store = DorisDwarfStore.load(
            manifest_path,
            config=config,
            verify_source=True,
            source_path=source,
        )
        try:
            profile = DorisServingProfile.from_config(
                config,
                source_id=store.manifest.source_identity.sha256,
                schema_version=store.manifest.schema_version,
            )
            registry_status = store.registry.status if store.registry is not None else "unknown"
            identity = AnalyticalModelEvidence(
                backend="doris",
                source_id=store.manifest.source_identity.sha256,
                manifest_sha256=sha256_file(store.manifest_path),
                manifest_schema_version=store.manifest.schema_version,
                database=config.database,
                table=config.table,
                serving_variant_id=profile.variant_id,
                registry_status=registry_status,
            )
            return cls(store, identity)
        except BaseException:
            store.close()
            raise

    @property
    def manifest(self) -> Any:
        """Expose the validated manifest for bounded report context."""
        return self._store.manifest

    @property
    def manifest_path(self) -> Path:
        return self._store.manifest_path

    def get_die(self, die_offset: int) -> Any:
        if self._batch_query is not None:
            return self._batch_query.get_die(die_offset)
        return self._store.get_die(die_offset)

    def find_locations(self, die_offset: int, *, attribute_name: str | None = None) -> Any:
        if self._batch_query is not None:
            return self._batch_query.find_locations(die_offset, attribute_name=attribute_name)
        return self._store.find_locations(die_offset, attribute_name=attribute_name)

    def find_frames(
        self, *, start_address: int | None = None, end_address: int | None = None
    ) -> Any:
        if self._batch_query is not None:
            return self._batch_query.find_frames(
                start_address=start_address,
                end_address=end_address,
            )
        return self._store.find_frames(
            start_address=start_address,
            end_address=end_address,
        )

    def prefetch_method_context(self, raw_methods: Sequence[dict[str, Any]]) -> QueryResult:
        """Load method context through bounded Doris family queries once."""
        requests = _method_context_requests(raw_methods)
        batches = batched_requests(requests)
        context_batches: list[MethodContextBatch] = []
        diagnostics: list[str] = []
        for batch in batches:
            query = self._store.find_method_context_batch(batch)
            diagnostics.extend(query.diagnostics[:1])
            if query.items and isinstance(query.items[0], MethodContextBatch):
                context_batches.append(query.items[0])
            else:
                context_batches.append(
                    MethodContextBatch(status=query.status, diagnostics=query.diagnostics)
                )
        merged = merge_context_batches(context_batches)
        self._batch_query = DorisBatchContextQuery(merged, self.manifest_path)
        summary = (
            f"Doris implementation context batches: {len(batches)}; "
            f"requests: {len(requests)}; status: {merged.status.value}; "
            "rows: "
            f"die={len(merged.die_rows)},attribute={len(merged.attribute_rows)},"
            f"reference={len(merged.reference_rows)},location={len(merged.location_rows)},"
            f"frame={len(merged.frame_rows)}"
        )
        diagnostics.append(summary)
        return QueryResult(
            merged.status,
            (merged,),
            (str(self.manifest_path),),
            tuple(dict.fromkeys(diagnostics)),
        )

    def close(self) -> None:
        """Close the Doris connection owned by the model."""
        self._store.close()


def load_doris_validation_model(
    manifest_path: Path | None,
    source: Path,
    diagnostics: list[str],
) -> tuple[
    DorisImplementationEvidenceModel | None,
    str | None,
    str | None,
    AnalyticalModelEvidence | None,
]:
    """Load a complete Doris model, never a file-backed row projection."""
    if manifest_path is None:
        diagnostics.append("no analytical DWARF store was supplied for method ABI context")
        return None, None, None, None
    try:
        model = DorisImplementationEvidenceModel.load(
            manifest_path.resolve(),
            source,
        )
        return (
            model,
            model.identity.manifest_sha256,
            model.identity.manifest_schema_version,
            model.identity,
        )
    except (OSError, ValueError, RuntimeError) as error:
        diagnostics.append(f"Doris analytical model could not be loaded: {type(error).__name__}")
        return None, None, None, None


def dwarf_method_evidence(
    store: Any | None,
    raw: dict[str, Any],
    start: int | None,
    end: int | None,
    frame_rows: tuple[dict[str, object], ...] | None = None,
) -> tuple[
    tuple[dict[str, object], ...],
    dict[str, Any],
    tuple[dict[str, object], ...],
    tuple[str, ...],
]:
    """Join method DIE attributes, parameter locations, and store-backed CFI."""
    if store is None:
        return (), {}, (), ("analytical DWARF store was not supplied",)
    implementation_offset, declaration_offset, die_offset = _method_offsets(raw)
    if die_offset is None:
        return (), {}, (), ("method has no DWARF implementation or declaration DIE offset",)
    try:
        return _query_method_context(store, start, end, frame_rows, die_offset, declaration_offset)
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        return (), {}, (), (f"analytical DWARF context query failed: {type(error).__name__}",)


def _method_offsets(raw: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    implementation = _optional_int(raw.get("selected_implementation_die_offset"))
    declaration = _optional_int(raw.get("declaration_die_offset"))
    return (
        implementation,
        declaration,
        implementation if implementation is not None else declaration,
    )


def _method_context_requests(
    raw_methods: Sequence[dict[str, Any]],
) -> tuple[MethodContextRequest, ...]:
    return tuple(
        MethodContextRequest(
            key=index,
            die_offsets=_context_die_offsets(raw),
            start_address=_optional_int(raw.get("selected_function_address")),
            end_address=_context_end(raw),
        )
        for index, raw in enumerate(raw_methods)
    )


def _context_die_offsets(raw: dict[str, Any]) -> tuple[int, ...]:
    values = (
        _optional_int(raw.get("selected_implementation_die_offset")),
        _optional_int(raw.get("declaration_die_offset")),
    )
    return tuple(value for value in dict.fromkeys(values) if value is not None)


def _context_end(raw: dict[str, Any]) -> int | None:
    start = _optional_int(raw.get("selected_function_address"))
    size = _optional_int(raw.get("selected_function_size"))
    if start is None or size is None or size <= 0:
        return None
    end = start + size
    return end if end < 1 << 64 else None


def _query_method_context(
    store: Any,
    start: int | None,
    end: int | None,
    frame_rows: tuple[dict[str, object], ...] | None,
    die_offset: int,
    declaration_offset: int | None,
) -> tuple[
    tuple[dict[str, object], ...],
    dict[str, Any],
    tuple[dict[str, object], ...],
    tuple[str, ...],
]:
    facts: dict[str, Any] = {"diagnostics": []}
    die = _query_die(store, die_offset, facts["diagnostics"])
    if die is None and declaration_offset is not None and declaration_offset != die_offset:
        die_offset = declaration_offset
        die = _query_die(store, die_offset, facts["diagnostics"])
    if die is None:
        return (), {}, (), (f"DIE 0x{die_offset:x} was not found in analytical store",)
    method_locations = _query_locations(store, die_offset, diagnostics=facts["diagnostics"])
    facts.update(_abi_facts(store, die, method_locations, facts["diagnostics"]))
    parameter_locations, parameter_facts = _parameter_evidence(store, die, facts["diagnostics"])
    facts.update(parameter_facts)
    locations = tuple(method_locations) + tuple(parameter_locations)
    frames = _context_frames(store, start, end, frame_rows, facts["diagnostics"])
    facts["diagnostics"].extend(_query_diagnostics(store, die_offset, frames))
    return (
        locations,
        facts,
        tuple(frames),
        tuple(dict.fromkeys(str(item) for item in facts["diagnostics"])),
    )


def _context_frames(
    store: Any,
    start: int | None,
    end: int | None,
    frame_rows: tuple[dict[str, object], ...] | None,
    diagnostics: list[str],
) -> list[dict[str, object]]:
    if start is None or end is None:
        return []
    if frame_rows is None:
        return _query_frames(store, start, end, diagnostics)
    return [row for row in frame_rows if _frame_overlaps(row, start, end)]


def store_cfi_status(
    frames: tuple[dict[str, object], ...], diagnostics: tuple[str, ...]
) -> EvidenceStatus:
    """Convert analytical-store CFI rows into a fail-closed status."""
    if not frames:
        return EvidenceStatus(ValidationStatus.NOT_OBSERVED, diagnostics)
    parser_statuses = {str(item.get("parser_status")) for item in frames}
    if parser_statuses - {"complete"}:
        return EvidenceStatus(
            ValidationStatus.PARTIAL,
            diagnostics + ("one or more analytical CFI rows are not complete",),
            {"covering_entries": len(frames)},
        )
    return EvidenceStatus(
        ValidationStatus.OBSERVED,
        diagnostics,
        {"covering_entries": len(frames), "source": "analytical-store"},
    )


def _query_die(store: Any, die_offset: int, diagnostics: list[str] | None = None) -> Any | None:
    result = store.get_die(die_offset)
    _record_query_status(result, f"DIE 0x{die_offset:x}", diagnostics)
    return result.items[0] if result.items else None


def _query_locations(
    store: Any,
    die_offset: int,
    attribute_name: str | None = None,
    *,
    diagnostics: list[str] | None = None,
) -> list[dict[str, object]]:
    result = store.find_locations(die_offset, attribute_name=attribute_name)
    _record_query_status(result, f"location DIE 0x{die_offset:x}", diagnostics)
    return [dict(item) for item in result.items if isinstance(item, dict)]


def _query_frames(
    store: Any,
    start: int | None,
    end: int | None,
    diagnostics: list[str] | None = None,
) -> list[dict[str, object]]:
    result = store.find_frames(start_address=start, end_address=end)
    _record_query_status(result, "CFI", diagnostics)
    return [dict(item) for item in result.items if isinstance(item, dict)]


def _frame_overlaps(row: dict[str, object], start: int | None, end: int | None) -> bool:
    if start is None or end is None:
        return True
    initial = _optional_int(row.get("initial_address"))
    span = _optional_int(row.get("address_range"))
    return initial is not None and span is not None and initial < end and initial + span > start


def _query_diagnostics(
    store: Any,
    die_offset: int,
    frames: list[dict[str, object]],
) -> list[str]:
    diagnostics: list[str] = []
    if not frames:
        diagnostics.append("analytical store has no CFI row covering the method range")
    result = store.find_locations(die_offset)
    _record_query_status(result, f"location DIE 0x{die_offset:x}", diagnostics)
    if getattr(result, "truncated", False):
        diagnostics.append("analytical store location query was truncated")
    return diagnostics


def _abi_facts(
    store: Any,
    die: Any,
    method_locations: list[dict[str, object]],
    diagnostics: list[str],
) -> dict[str, Any]:
    attributes = getattr(die, "attributes", {})
    facts: dict[str, Any] = {
        "diagnostics": list(diagnostics),
        "calling_convention": _attribute_text(attributes, "DW_AT_calling_convention"),
        "object_pointer": _object_pointer_name(die),
        "frame_base_locations": _location_summaries(
            item for item in method_locations if item.get("attribute_name") == "DW_AT_frame_base"
        ),
        "return_location": _location_summary_for_attribute(
            store, int(die.offset), "DW_AT_return_location", diagnostics
        ),
    }
    if facts["calling_convention"] is None:
        facts["diagnostics"].append("DW_AT_calling_convention is absent")
    if facts["object_pointer"] is None:
        facts["diagnostics"].append("DW_AT_object_pointer is absent")
    return facts


def _parameter_evidence(
    store: Any, die: Any, diagnostics: list[str]
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    locations: list[dict[str, object]] = []
    parameter_locations: list[str] = []
    artificial: list[str] = []
    hidden: list[str] = []
    object_pointer = _object_pointer_name(die)
    for child in die.iter_children():
        if getattr(child, "tag", None) != "DW_TAG_formal_parameter":
            continue
        attributes = getattr(child, "attributes", {})
        offset = getattr(child, "offset", None)
        if not isinstance(offset, int):
            continue
        name = _attribute_text(attributes, "DW_AT_name") or f"die:0x{offset:x}"
        is_artificial = _attribute_bool(attributes, "DW_AT_artificial") is True
        if is_artificial:
            artificial.append(name)
            if name != object_pointer and name.lower() not in {"this", "__this"}:
                hidden.append(name)
        child_locations = _query_locations(store, offset, "DW_AT_location", diagnostics=diagnostics)
        for record in child_locations:
            enriched = dict(record)
            enriched["parameter_name"] = name
            enriched["parameter_die_offset"] = offset
            enriched["artificial"] = is_artificial
            locations.append(enriched)
        if child_locations:
            parameter_locations.append(f"{name}:" + ",".join(_location_summaries(child_locations)))
    return locations, {
        "parameter_locations": tuple(parameter_locations),
        "artificial_parameters": tuple(artificial),
        "hidden_parameters": tuple(hidden),
        "hidden_return": _hidden_return_value(hidden),
    }


def _object_pointer_name(die: Any) -> str | None:
    target_getter = getattr(die, "get_DIE_from_attribute", None)
    target = target_getter("DW_AT_object_pointer") if callable(target_getter) else None
    if target is None:
        return None
    attributes = getattr(target, "attributes", {})
    offset = getattr(target, "offset", None)
    return _attribute_text(attributes, "DW_AT_name") or (
        f"die:0x{offset:x}" if isinstance(offset, int) else "object-pointer-die"
    )


def _location_summary_for_attribute(
    store: Any, die_offset: int, name: str, diagnostics: list[str]
) -> str | None:
    values = _query_locations(store, die_offset, name, diagnostics=diagnostics)
    summaries = _location_summaries(values)
    return summaries[0] if summaries else None


def _location_summaries(values: Any) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        expression = _location_expression(value)
        result.append(json.dumps(expression, sort_keys=True, default=str))
    return tuple(result)


def _location_expression(value: dict[str, object]) -> object:
    """Select the logical expression from either Doris or legacy row shapes."""
    for key in ("expression", "details", "decoded_value"):
        candidate = value.get(key)
        if candidate is not None:
            return candidate
    encoded = value.get("expression_json")
    if isinstance(encoded, str):
        try:
            return json.loads(encoded)
        except json.JSONDecodeError:
            return encoded
    return None


def _hidden_return_value(hidden: list[str]) -> bool | None:
    matches = [value for value in hidden if "sret" in value.lower() or "return" in value.lower()]
    return True if matches else None


def _attribute_text(attributes: Any, name: str) -> str | None:
    if not isinstance(attributes, dict):
        return None
    attribute = attributes.get(name)
    value = getattr(attribute, "value", None)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else None


def _attribute_bool(attributes: Any, name: str) -> bool | None:
    if not isinstance(attributes, dict):
        return None
    value = getattr(attributes.get(name), "value", None)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _record_query_status(result: QueryResult, label: str, diagnostics: list[str] | None) -> None:
    if diagnostics is None:
        return
    status = result.status.value
    if status == "complete":
        return
    diagnostics.extend(result.diagnostics)
    diagnostics.append(f"{label} query status: {status}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "DorisImplementationEvidenceModel",
    "dwarf_method_evidence",
    "load_doris_validation_model",
    "sha256_file",
    "store_cfi_status",
]

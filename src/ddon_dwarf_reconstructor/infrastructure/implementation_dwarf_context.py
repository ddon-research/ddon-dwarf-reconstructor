"""Analytical-store context for source-bound implementation validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.content_hash import sha256_file
from ..domain.models.analytical_dwarf import MethodContextBatch, MethodContextRequest, QueryResult
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
from .implementation_dwarf_context_evidence import (
    abi_facts as _abi_facts,
)
from .implementation_dwarf_context_evidence import (
    frame_overlaps as _frame_overlaps,
)
from .implementation_dwarf_context_evidence import (
    optional_int as _optional_int,
)
from .implementation_dwarf_context_evidence import (
    parameter_evidence as _parameter_evidence,
)
from .implementation_dwarf_context_evidence import (
    query_diagnostics as _query_diagnostics,
)
from .implementation_dwarf_context_evidence import (
    query_die as _query_die,
)
from .implementation_dwarf_context_evidence import (
    query_frames as _query_frames,
)
from .implementation_dwarf_context_evidence import (
    query_locations as _query_locations,
)


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

    def get_die(self, die_offset: int, *, unit_offset: int | None = None) -> Any:
        if self._batch_query is not None:
            return self._batch_query.get_die(die_offset, unit_offset=unit_offset)
        return self._store.get_die(die_offset)

    def find_locations(
        self,
        die_offset: int,
        *,
        unit_offset: int | None = None,
        attribute_name: str | None = None,
    ) -> Any:
        if self._batch_query is not None:
            return self._batch_query.find_locations(
                die_offset,
                unit_offset=unit_offset,
                attribute_name=attribute_name,
            )
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
    (
        implementation_offset,
        declaration_offset,
        die_offset,
        implementation_unit,
        declaration_unit,
    ) = _method_offsets(raw)
    if die_offset is None:
        return (), {}, (), ("method has no DWARF implementation or declaration DIE offset",)
    try:
        return _query_method_context(
            store,
            start,
            end,
            frame_rows,
            die_offset,
            declaration_offset,
            implementation_unit,
            declaration_unit,
        )
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        return (), {}, (), (f"analytical DWARF context query failed: {type(error).__name__}",)


def _method_offsets(
    raw: dict[str, Any],
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    implementation = _optional_int(raw.get("selected_implementation_die_offset"))
    declaration = _optional_int(raw.get("declaration_die_offset"))
    return (
        implementation,
        declaration,
        implementation if implementation is not None else declaration,
        _selected_implementation_cu_offset(raw, implementation),
        _optional_int(raw.get("declaration_cu_offset")),
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
            unit_offsets=_context_unit_offsets(raw),
        )
        for index, raw in enumerate(raw_methods)
    )


def _context_die_offsets(raw: dict[str, Any]) -> tuple[int, ...]:
    values = (
        _optional_int(raw.get("selected_implementation_die_offset")),
        _optional_int(raw.get("declaration_die_offset")),
    )
    return tuple(value for value in dict.fromkeys(values) if value is not None)


def _context_unit_offsets(raw: dict[str, Any]) -> tuple[int | None, ...]:
    """Align implementation/declaration CU provenance with requested DIE offsets."""
    implementation = _optional_int(raw.get("selected_implementation_die_offset"))
    declaration = _optional_int(raw.get("declaration_die_offset"))
    implementation_unit = _selected_implementation_cu_offset(raw, implementation)
    declaration_unit = _optional_int(raw.get("declaration_cu_offset"))
    units: list[int | None] = []
    for offset in _context_die_offsets(raw):
        units.append(
            implementation_unit
            if offset == implementation
            else declaration_unit
            if offset == declaration
            else None
        )
    return tuple(units)


def _selected_implementation_cu_offset(
    raw: dict[str, Any], implementation_offset: int | None
) -> int | None:
    direct = _optional_int(raw.get("implementation_cu_offset"))
    if direct is not None:
        return direct
    for candidate in raw.get("candidates", ()):
        if not isinstance(candidate, dict):
            continue
        if _optional_int(candidate.get("implementation_die_offset")) == implementation_offset:
            return _optional_int(candidate.get("implementation_cu_offset"))
    return None


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
    implementation_unit: int | None,
    declaration_unit: int | None,
) -> tuple[
    tuple[dict[str, object], ...],
    dict[str, Any],
    tuple[dict[str, object], ...],
    tuple[str, ...],
]:
    facts: dict[str, Any] = {"diagnostics": []}
    die = _query_die(store, die_offset, implementation_unit, facts["diagnostics"])
    declaration_die = (
        _query_die(store, declaration_offset, declaration_unit, facts["diagnostics"])
        if declaration_offset is not None and declaration_offset != die_offset
        else die
    )
    if die is None and declaration_offset is not None and declaration_offset != die_offset:
        die_offset = declaration_offset
        implementation_unit = declaration_unit
        die = _query_die(store, die_offset, implementation_unit, facts["diagnostics"])
    if die is None:
        return (), {}, (), (f"DIE 0x{die_offset:x} was not found in analytical store",)
    method_locations = _query_locations(
        store,
        die_offset,
        unit_offset=implementation_unit,
        diagnostics=facts["diagnostics"],
    )
    facts.update(
        _abi_facts(
            store,
            die,
            declaration_die,
            method_locations,
            implementation_unit,
            facts["diagnostics"],
        )
    )
    parameter_locations, parameter_facts = _parameter_evidence(
        store,
        die,
        implementation_unit,
        facts["diagnostics"],
    )
    facts.update(parameter_facts)
    locations = tuple(method_locations) + tuple(parameter_locations)
    frames = _context_frames(store, start, end, frame_rows, facts["diagnostics"])
    facts["diagnostics"].extend(_query_diagnostics(store, die_offset, implementation_unit, frames))
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


__all__ = [
    "DorisImplementationEvidenceModel",
    "dwarf_method_evidence",
    "load_doris_validation_model",
    "sha256_file",
    "store_cfi_status",
]

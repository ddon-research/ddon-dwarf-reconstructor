"""Bounded Doris implementation-context projection tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    MethodContextRequest,
    QueryStatus,
)
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    AnalyticalModelEvidence,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_method_context import (
    DorisBatchContextQuery,
    batched_requests,
    query_method_context_batch,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_dwarf_context import (
    DorisImplementationEvidenceModel,
    dwarf_method_evidence,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _BatchStore:
    manifest_path = Path("manifest.json")
    manifest = SimpleNamespace(status="complete")
    _config = SimpleNamespace(die_lookup_table="records_die")

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._dies = (
            {
                "unit_offset": 1,
                "die_offset": 10,
                "ordinal": 1,
                "tag": "DW_TAG_subprogram",
                "abbrev_code": 1,
                "has_children": True,
                "depth": 1,
                "parent_offset": 2,
                "is_null": False,
            },
            {
                "unit_offset": 1,
                "die_offset": 11,
                "ordinal": 2,
                "tag": "DW_TAG_formal_parameter",
                "abbrev_code": 2,
                "has_children": False,
                "depth": 2,
                "parent_offset": 10,
                "is_null": False,
            },
            {
                "unit_offset": 1,
                "die_offset": 12,
                "ordinal": 3,
                "tag": "DW_TAG_variable",
                "abbrev_code": 3,
                "has_children": False,
                "depth": 2,
                "parent_offset": 10,
                "is_null": False,
            },
        )

    def _rows(
        self,
        family: str,
        filters: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> tuple[dict[str, object], ...]:
        values = filters or {}
        self.calls.append((family, values))
        return {
            "die": self._die_rows(values),
            "attribute": self._attribute_rows(),
            "reference": self._reference_rows(),
            "location": self._location_rows(),
        }.get(family, ())

    def _die_rows(self, filters: dict[str, object]) -> tuple[dict[str, object], ...]:
        if "parent_offset" in filters:
            return (self._dies[1],)
        wanted = set(filters.get("die_offset", ()))
        return tuple(row for row in self._dies if row["die_offset"] in wanted)

    @staticmethod
    def _attribute_rows() -> tuple[dict[str, object], ...]:
        return (
            {
                "unit_offset": 1,
                "die_offset": 10,
                "ordinal": 0,
                "name": "DW_AT_calling_convention",
                "form": "DW_FORM_data1",
                "decoded_value": "DW_CC_normal",
            },
            {
                "unit_offset": 1,
                "die_offset": 11,
                "ordinal": 0,
                "name": "DW_AT_name",
                "form": "DW_FORM_string",
                "decoded_value": "sret",
            },
            {
                "unit_offset": 1,
                "die_offset": 11,
                "ordinal": 1,
                "name": "DW_AT_artificial",
                "form": "DW_FORM_flag",
                "decoded_value": True,
            },
            {
                "unit_offset": 1,
                "die_offset": 12,
                "ordinal": 0,
                "name": "DW_AT_name",
                "form": "DW_FORM_string",
                "decoded_value": "this",
            },
        )

    @staticmethod
    def _reference_rows() -> tuple[dict[str, object], ...]:
        return (
            {
                "unit_offset": 1,
                "die_offset": 10,
                "attribute_name": "DW_AT_object_pointer",
                "relation": "attribute_reference",
                "target_offset": 12,
            },
        )

    @staticmethod
    def _location_rows() -> tuple[dict[str, object], ...]:
        return (
            {
                "unit_offset": 1,
                "die_offset": 10,
                "ordinal": 0,
                "record_offset": 1,
                "attribute_name": "DW_AT_frame_base",
                "expression": ["rsp"],
            },
            {
                "unit_offset": 1,
                "die_offset": 10,
                "ordinal": 1,
                "record_offset": 2,
                "attribute_name": "DW_AT_return_location",
                "expression": ["rax"],
            },
            {
                "unit_offset": 1,
                "die_offset": 11,
                "ordinal": 0,
                "record_offset": 3,
                "attribute_name": "DW_AT_location",
                "expression": ["rdx"],
            },
        )

    class _Queries:
        def frame_rows_overlapping(
            self,
            _start: int,
            _end: int,
            *,
            columns: tuple[str, ...],
            order_by: tuple[str, ...],
        ) -> tuple[dict[str, object], ...]:
            del columns, order_by
            return (
                {
                    "record_type": "frame",
                    "section_name": ".eh_frame",
                    "record_offset": 1,
                    "record_length": 16,
                    "frame_kind": "FDE",
                    "initial_address": 0x1000,
                    "address_range": 0x20,
                    "parser_status": "complete",
                    "details_json": None,
                },
            )

    _queries = _Queries()

    def find_method_context_batch(self, requests: tuple[MethodContextRequest, ...]):
        return query_method_context_batch(self, requests)


def test_context_projection_batches_families_and_keeps_doris_as_authority() -> None:
    store = _BatchStore()
    result = query_method_context_batch(
        store,
        (MethodContextRequest(0, (10,), 0x1000, 0x1010),),
    )

    assert result.status is QueryStatus.COMPLETE
    batch = result.items[0]
    assert batch.die_rows
    assert {row["die_offset"] for row in batch.die_rows} == {10, 11, 12}
    assert {family for family, _filters in store.calls} == {
        "die",
        "reference",
        "attribute",
        "location",
    }
    assert len([call for call in store.calls if call[0] == "die"]) == 3


def test_batch_query_replays_existing_method_context_semantics() -> None:
    store = _BatchStore()
    result = query_method_context_batch(
        store,
        (MethodContextRequest(0, (10,), 0x1000, 0x1010),),
    )
    query = DorisBatchContextQuery(result.items[0], store.manifest_path)

    locations, facts, frames, diagnostics = dwarf_method_evidence(
        query,
        {"selected_implementation_die_offset": 10},
        0x1000,
        0x1010,
    )

    assert len(locations) == 3
    assert facts["object_pointer"] == "this"
    assert facts["hidden_parameters"] == ("sret",)
    assert facts["hidden_return"] is True
    assert len(frames) == 1
    assert diagnostics == ()


def test_context_request_batches_are_stable_and_bounded() -> None:
    requests = tuple(MethodContextRequest(index, (index,)) for index in range(1_025))

    batches = batched_requests(requests, size=512)

    assert tuple(len(batch) for batch in batches) == (512, 512, 1)
    assert tuple(item.key for batch in batches for item in batch) == tuple(range(1_025))


def test_model_prefetch_routes_all_follow_up_context_queries_to_the_batch_view() -> None:
    store = _BatchStore()
    model = DorisImplementationEvidenceModel(
        store,
        AnalyticalModelEvidence(
            backend="doris",
            source_id="a" * 64,
            manifest_sha256="b" * 64,
            manifest_schema_version="1.1",
            database="dwarf",
            table="records",
            serving_variant_id="canonical",
            registry_status="complete",
        ),
    )

    result = model.prefetch_method_context(
        [
            {
                "selected_implementation_die_offset": 10,
                "selected_function_address": 0x1000,
                "selected_function_size": 0x10,
            }
        ]
    )
    calls_after_prefetch = len(store.calls)
    dwarf_method_evidence(
        model,
        {"selected_implementation_die_offset": 10},
        0x1000,
        0x1010,
    )

    assert result.status is QueryStatus.COMPLETE
    assert any("batches: 1; requests: 1" in item for item in result.diagnostics)
    assert len(store.calls) == calls_after_prefetch

"""Analytical session boundaries for store-backed runtime lookup."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.application.generation import resolve_explicit_validation_dump
from ddon_dwarf_reconstructor.domain.services.definition_selection import NestedTypeCounts
from ddon_dwarf_reconstructor.infrastructure.analytical.bounded_query_cache import (
    BoundedQueryCache,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_layout import UNIT_BUCKET_SIZE
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_store import ParquetDwarfStore
from ddon_dwarf_reconstructor.infrastructure.analytical.session import AnalyticalDwarfSession

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_store_session_accepts_only_explicit_legacy_dump_configuration(tmp_path: Path) -> None:
    session = AnalyticalDwarfSession(tmp_path / "manifest.json")
    generator = SimpleNamespace(
        session=session,
        _configured_dwarf_dump_path=tmp_path / "explicit.zst",
        exhaustive_search=True,
        elf_path=tmp_path / "sample.elf",
    )

    assert (
        resolve_explicit_validation_dump(generator._configured_dwarf_dump_path)
        == tmp_path / "explicit.zst"
    )


def test_parquet_store_exposes_typed_compilation_units() -> None:
    store = object.__new__(ParquetDwarfStore)
    store.manifest = SimpleNamespace(source_identity=SimpleNamespace(sha256="source"))
    store._payload_rows = lambda _filters: [
        {
            "source_id": "source",
            "unit_offset": 0x20,
            "unit_length": 64,
            "unit_type": "DW_UT_compile",
            "header": {"version": 4},
        }
    ]

    units = list(store.iter_compilation_units())

    assert units[0].unit_offset == 0x20
    assert units[0].unit_length == 64
    assert units[0].unit_type == "DW_UT_compile"
    assert units[0].header == {"version": 4}


def test_parquet_definition_lookup_prefers_complete_definition() -> None:
    class _Die:
        def __init__(self, offset: int, declaration: bool) -> None:
            self.offset = offset
            self.tag = "DW_TAG_class_type"
            self.has_children = False
            self.depth = 0
            self.cu = SimpleNamespace(cu_offset=0x10)
            self.attributes = {"DW_AT_declaration": object()} if declaration else {}

        def iter_children(self):
            return ()

        def get_full_path(self) -> str:
            return "Thing"

        def child_tag_counts(self) -> NestedTypeCounts:
            return NestedTypeCounts(enums=0, structs=0, unions=0)

    declaration = _Die(0x20, True)
    definition = _Die(0x40, False)
    store = object.__new__(ParquetDwarfStore)
    store.manifest_path = Path("manifest.json")
    store.manifest = SimpleNamespace(
        source_identity=SimpleNamespace(sha256="source"), status="complete"
    )
    store._definition_query_cache = BoundedQueryCache()
    store._selection_cache = None
    store._die_cache = {}
    calls: list[dict[str, object]] = []

    def rows(filters: dict[str, object], **_options: object) -> list[dict[str, object]]:
        calls.append(filters)
        return [
            {"die_offset": declaration.offset, "unit_offset": 0x10, "ordinal": 0},
            {"die_offset": definition.offset, "unit_offset": 0x10, "ordinal": 1},
        ]

    store._payload_rows = rows
    store.die_by_offset = lambda offset: {
        declaration.offset: declaration,
        definition.offset: definition,
    }.get(offset)
    store._dies_for_index_records = lambda records: tuple(
        store.die_by_offset(int(record["die_offset"])) for record in records
    )
    store._prime_child_tag_counts = lambda _dies: None

    result = store.find_definitions(
        "Thing",
        qualified_name="Thing",
        tags=frozenset({"DW_TAG_class_type"}),
    )
    cached_result = store.find_definitions(
        "Thing",
        qualified_name="Thing",
        tags=frozenset({"DW_TAG_class_type"}),
    )

    assert [item.offset for item in result.items] == [0x40, 0x20]
    assert cached_result is result
    assert len(calls) == 1


def test_parquet_batch_definition_hydration_preserves_duplicate_index_rows() -> None:
    die = object()
    store = object.__new__(ParquetDwarfStore)
    store._die_cache = {}

    def rows(filters: dict[str, object]) -> list[dict[str, object]]:
        if filters["record_type"] == "die":
            return [{"unit_offset": 0x10, "die_offset": 0x20}]
        return []

    store._payload_rows = rows
    store._die_from_record = lambda record, attributes=None: store._die_cache.setdefault(
        int(record["die_offset"]), die
    )

    records = [
        {"unit_offset": 0x10, "die_offset": 0x20},
        {"unit_offset": 0x10, "die_offset": 0x20},
    ]

    assert store._dies_for_index_records(records) == (die, die)


def test_parquet_index_hydration_batches_attributes_by_unit_bucket() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._die_cache = {}
    calls: list[dict[str, object]] = []
    records = [
        {"unit_offset": 0x10, "die_offset": 0x20},
        {"unit_offset": 0x20, "die_offset": 0x30},
        {"unit_offset": UNIT_BUCKET_SIZE + 1, "die_offset": 0x40},
    ]

    def rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        if filters["record_type"] == "die":
            return [
                {"unit_offset": item["unit_offset"], "die_offset": item["die_offset"]}
                for item in records
            ]
        return []

    store._payload_rows = rows
    store._die_from_record = lambda record, attributes=None: store._die_cache.setdefault(
        int(record["die_offset"]), object()
    )

    assert len(store._dies_for_index_records(records)) == 3
    assert calls == [
        {
            "record_type": "die",
            "unit_offset": (0x10, 0x20),
            "unit_bucket": 0,
            "die_offset": (0x20, 0x30),
        },
        {
            "record_type": "die",
            "unit_offset": (UNIT_BUCKET_SIZE + 1,),
            "unit_bucket": 1,
            "die_offset": (0x40,),
        },
        {
            "record_type": "attribute",
            "unit_offset": (0x10, 0x20),
            "unit_bucket": 0,
            "die_offset": (0x20, 0x30),
        },
        {
            "record_type": "attribute",
            "unit_offset": (UNIT_BUCKET_SIZE + 1,),
            "unit_bucket": 1,
            "die_offset": (0x40,),
        },
    ]


def test_parquet_index_hydration_falls_back_after_zstd_scan_error() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._die_cache = {}
    calls: list[dict[str, object]] = []
    records = [
        {"unit_offset": 0x10, "die_offset": 0x20},
        {"unit_offset": 0x10, "die_offset": 0x30},
    ]

    def rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        if filters["record_type"] == "die":
            return records
        if isinstance(filters["unit_offset"], tuple) or len(filters["die_offset"]) > 1:
            raise OSError("ZSTD decompression failed: Data corruption detected")
        return []

    store._payload_rows = rows
    store._die_from_record = lambda record, attributes=None: store._die_cache.setdefault(
        int(record["die_offset"]), object()
    )

    assert len(store._dies_for_index_records(records)) == 2
    assert calls == [
        {
            "record_type": "die",
            "unit_offset": (0x10,),
            "unit_bucket": 0,
            "die_offset": (0x20, 0x30),
        },
        {
            "record_type": "attribute",
            "unit_offset": (0x10,),
            "unit_bucket": 0,
            "die_offset": (0x20, 0x30),
        },
        {
            "record_type": "attribute",
            "unit_offset": 0x10,
            "unit_bucket": 0,
            "die_offset": (0x20, 0x30),
        },
        {
            "record_type": "attribute",
            "unit_offset": 0x10,
            "unit_bucket": 0,
            "die_offset": (0x20,),
        },
        {
            "record_type": "attribute",
            "unit_offset": 0x10,
            "unit_bucket": 0,
            "die_offset": (0x30,),
        },
    ]


def test_parquet_child_tag_counts_projects_tags_and_caches() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._child_tag_counts = {}
    store._die_cache = {}
    calls: list[tuple[dict[str, object], tuple[str, ...]]] = []

    def rows(filters: dict[str, object], columns: tuple[str, ...]) -> list[dict[str, object]]:
        calls.append((filters, columns))
        return [
            {"tag": "DW_TAG_structure_type", "is_null": False},
            {"tag": "DW_TAG_union_type", "is_null": False},
            {"tag": "DW_TAG_enumeration_type", "is_null": False},
            {"tag": "DW_TAG_base_type", "is_null": False},
            {"tag": "DW_TAG_structure_type", "is_null": True},
        ]

    store._rows = rows

    assert store.child_tag_counts(0x20) == NestedTypeCounts(enums=1, structs=1, unions=1)
    assert store.child_tag_counts(0x20) == NestedTypeCounts(enums=1, structs=1, unions=1)
    assert calls == [({"record_type": "die", "parent_offset": 0x20}, ("tag", "is_null"))]


def test_parquet_definition_ranking_primes_child_counts_in_one_scan() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._child_tag_counts = {}
    store._datasets = {}
    calls: list[tuple[dict[str, object], tuple[str, ...]]] = []

    def rows(filters: dict[str, object], columns: tuple[str, ...]) -> list[dict[str, object]]:
        calls.append((filters, columns))
        return [
            {"parent_offset": 0x20, "tag": "DW_TAG_structure_type", "is_null": False},
            {"parent_offset": 0x40, "tag": "DW_TAG_union_type", "is_null": False},
            {"parent_offset": 0x40, "tag": "DW_TAG_enumeration_type", "is_null": False},
            {"parent_offset": 0x40, "tag": "DW_TAG_structure_type", "is_null": True},
        ]

    store._rows = rows
    store._prime_child_tag_counts(
        (
            SimpleNamespace(offset=0x20, cu=SimpleNamespace(cu_offset=0x10)),
            SimpleNamespace(offset=0x40, cu=SimpleNamespace(cu_offset=0x20)),
        )
    )

    assert store._child_tag_counts == {
        0x20: NestedTypeCounts(structs=1),
        0x40: NestedTypeCounts(enums=1, unions=1),
    }
    assert calls == [
        (
            {
                "record_type": "die",
                "unit_offset": (0x10, 0x20),
                "unit_bucket": 0,
                "parent_offset": (0x20, 0x40),
            },
            ("parent_offset", "tag", "is_null"),
        )
    ]


def test_parquet_attribute_target_adds_known_cu_partition_filter() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._die_cache = {0x20: SimpleNamespace(cu=SimpleNamespace(cu_offset=0x10))}
    store._reference_targets = {}
    store._reference_units_loaded = set()
    calls: list[dict[str, object]] = []

    def rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        return [
            {
                "relation": "attribute_reference",
                "die_offset": 0x20,
                "attribute_name": "DW_AT_type",
                "target_offset": 0x40,
            }
        ]

    store._payload_rows = rows

    assert store.attribute_target(0x20, "DW_AT_type") == 0x40
    assert calls == [{"record_type": "reference", "unit_offset": 0x10}]


def test_parquet_children_adds_known_cu_partition_filter() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._children_cache = {}
    store._die_cache = {0x20: SimpleNamespace(cu=SimpleNamespace(cu_offset=0x10))}
    calls: list[dict[str, object]] = []
    store._payload_rows = lambda filters: calls.append(filters) or []

    assert tuple(store.children_for_die(0x20)) == ()
    assert calls == [{"record_type": "die", "parent_offset": 0x20, "unit_offset": 0x10}]


def test_parquet_references_adds_known_cu_partition_filter() -> None:
    store = object.__new__(ParquetDwarfStore)
    store.manifest_path = Path("manifest.json")
    store.manifest = SimpleNamespace(status="complete")
    store._die_cache = {0x20: SimpleNamespace(cu=SimpleNamespace(cu_offset=0x10))}
    calls: list[dict[str, object]] = []
    store._payload_rows = lambda filters: (
        calls.append(filters) or [{"relation": "attribute_reference", "target_offset": 0x40}]
    )

    result = store.references(0x20)

    assert result.status.value == "complete"
    assert result.items == ({"relation": "attribute_reference", "target_offset": 0x40},)
    assert calls == [{"record_type": "reference", "die_offset": 0x20, "unit_offset": 0x10}]

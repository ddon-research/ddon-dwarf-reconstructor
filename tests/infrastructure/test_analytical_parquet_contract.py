"""Typed Parquet value and publication-contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationManifest,
)
from ddon_dwarf_reconstructor.infrastructure.analytical import (
    AnalyticalDwarfSession,
    JsonlDwarfStore,
    ParquetDwarfStore,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.manifest import (
    declared_parquet_files,
    validate_manifest_files,
    validate_parquet_payloads,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.materializer import DwarfMaterializer
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_rows import (
    normalize_record,
    restore_record,
    schema_for,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.session import load_analytical_store
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog
from tests.infrastructure.test_analytical_store import _fixture_dwarf, _Session

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_typed_parquet_values_preserve_unsigned_dwarf_integers() -> None:
    value = 2**64 - 1
    record = {
        "record_type": "attribute",
        "source_id": "a" * 64,
        "unit_offset": 0,
        "die_offset": 0,
        "ordinal": 0,
        "name": "DW_AT_const_value",
        "form": "DW_FORM_udata",
        "raw_value": value,
        "decoded_value": value,
    }

    row = normalize_record(record)
    restored = restore_record(row)

    assert row["raw_value_kind"] == "uint"
    assert row["raw_value_uint"] == value
    assert restored["raw_value"] == value


@pytest.mark.parametrize(
    "kind",
    ("range", "location", "line", "macro", "frame", "abbreviation", "name"),
)
def test_semantic_record_families_have_typed_round_trip(kind: str) -> None:
    import pyarrow

    record = {
        "record_type": kind,
        "source_id": "a" * 64,
        "unit_offset": 0,
        "die_offset": 0,
        "ordinal": 0,
        "record_offset": 0,
        "name": "Thing",
        "details": {"raw": [0, 1]},
    }

    row = normalize_record(record)
    restored = restore_record(row)

    assert schema_for(pyarrow, kind)
    assert restored["record_type"] == kind
    assert "unit_bucket" not in restored


def test_complete_manifest_verifies_parquet_hash_and_footer_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(source, tmp_path / "store-root", write_parquet=True)
        )

    assert materializer.last_manifest_path is not None
    manifest_path = materializer.last_manifest_path
    payload = json.loads(manifest_path.read_text())
    manifest = MaterializationManifest.from_dict(payload)
    validate_manifest_files(manifest_path, manifest, verify_hashes=True)
    payload["artifacts"][0]["sha256"] = "0" * 64
    stale_manifest = MaterializationManifest.from_dict(payload)
    with pytest.raises(ValueError, match="changed"):
        validate_manifest_files(manifest_path, stale_manifest, verify_hashes=True)
    del payload["artifacts"]
    legacy_manifest = MaterializationManifest.from_dict(payload)
    with pytest.raises(ValueError, match="closed artifact metadata"):
        validate_manifest_files(manifest_path, legacy_manifest)


def test_declared_parquet_files_rejects_complete_projection_drift(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(source, tmp_path / "store-root", write_parquet=True)
        )

    assert materializer.last_manifest_path is not None
    manifest_path = materializer.last_manifest_path
    manifest = MaterializationManifest.from_dict(json.loads(manifest_path.read_text()))
    declared = declared_parquet_files(manifest_path, manifest)
    assert declared == tuple(sorted(path.resolve() for path in declared))

    extra = manifest_path.parent / "parquet" / "index" / "part-extra.parquet"
    extra.write_bytes(declared[0].read_bytes())
    with pytest.raises(ValueError, match="does not match"):
        declared_parquet_files(manifest_path, manifest)


def test_declared_parquet_files_rejects_duplicate_checkpoint_paths(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(source, tmp_path / "store-root", write_parquet=True)
        )

    assert materializer.last_manifest_path is not None
    manifest_path = materializer.last_manifest_path
    payload = json.loads(manifest_path.read_text())
    relative = payload["artifacts"][0]["path"]
    payload["configuration"]["parquet_files"] = [relative, relative]
    checkpoint = MaterializationManifest.from_dict(payload)
    with pytest.raises(ValueError, match="duplicate configured"):
        declared_parquet_files(manifest_path, checkpoint)


def test_index_die_hydration_prunes_parquet_reads_by_cu_bucket() -> None:
    store = object.__new__(ParquetDwarfStore)
    calls: list[dict[str, object]] = []

    def payload_rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        return []

    store._payload_rows = payload_rows
    missing_keys = ((0x20, 0x30), (0x1000020, 0x1000030))

    rows = store._die_rows_by_bucket(missing_keys)

    assert rows == []
    assert calls == [
        {
            "record_type": "die",
            "unit_offset": (0x20,),
            "unit_bucket": 0,
            "die_offset": (0x30,),
        },
        {
            "record_type": "die",
            "unit_offset": (0x1000020,),
            "unit_bucket": 1,
            "die_offset": (0x1000030,),
        },
    ]


def test_die_lookup_uses_the_containing_cu_bucket() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._die_cache = {}
    store._die_unit_offsets = {}
    store._unit_ranges = ((0x20, 0x40),)
    calls: list[dict[str, object]] = []

    def payload_rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        return [
            {
                "unit_offset": 0x20,
                "die_offset": 0x30,
                "ordinal": 1,
                "tag": "DW_TAG_structure_type",
                "has_children": False,
                "depth": 0,
                "is_null": False,
            }
        ]

    store._payload_rows = payload_rows
    store._die_from_record = lambda record: record

    assert store.die_by_offset(0x30) is not None
    assert calls == [
        {
            "record_type": "die",
            "die_offset": 0x30,
            "unit_offset": 0x20,
            "unit_bucket": 0,
        }
    ]


def test_definition_child_count_priming_prunes_by_candidate_cu_bucket() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._child_tag_counts = {}
    store._datasets = {"die": object()}
    calls: list[dict[str, object]] = []

    def rows(filters: dict[str, object], columns: tuple[str, ...]) -> list[dict[str, object]]:
        calls.append(filters)
        assert columns == ("parent_offset", "tag", "is_null")
        return []

    store._rows = rows
    dies = [
        SimpleNamespace(offset=0x30, cu=SimpleNamespace(cu_offset=0x20)),
        SimpleNamespace(offset=0x1000030, cu=SimpleNamespace(cu_offset=0x1000020)),
    ]

    store._prime_child_tag_counts(dies)

    assert calls == [
        {
            "record_type": "die",
            "unit_offset": (0x20,),
            "unit_bucket": 0,
            "parent_offset": (0x30,),
        },
        {
            "record_type": "die",
            "unit_offset": (0x1000020,),
            "unit_bucket": 1,
            "parent_offset": (0x1000030,),
        },
    ]


def test_child_hydration_batches_attributes_by_cu_bucket() -> None:
    store = object.__new__(ParquetDwarfStore)
    store._children_cache = {}
    store._die_cache = {}
    store._die_unit_offsets = {}
    store._reference_targets = {}
    store._reference_units_loaded = set()
    calls: list[dict[str, object]] = []

    def payload_rows(filters: dict[str, object]) -> list[dict[str, object]]:
        calls.append(filters)
        if filters["record_type"] == "die":
            return [
                {
                    "unit_offset": 0x20,
                    "die_offset": 0x30,
                    "ordinal": 1,
                    "tag": "DW_TAG_member",
                    "has_children": False,
                    "depth": 1,
                    "is_null": False,
                    "parent_offset": 0x10,
                }
            ]
        return []

    store._payload_rows = payload_rows
    store._die_from_record = lambda record, attributes=(): record
    store._die_cache[0x10] = SimpleNamespace(cu=SimpleNamespace(cu_offset=0x20))

    tuple(store.children_for_die(0x10))

    assert calls == [
        {
            "record_type": "die",
            "parent_offset": 0x10,
            "unit_offset": 0x20,
        },
        {
            "record_type": "attribute",
            "unit_offset": (0x20,),
            "unit_bucket": 0,
            "die_offset": (0x30,),
        },
    ]


def test_materializer_does_not_reuse_a_complete_store_with_an_old_schema(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    request = DwarfMaterializationRequest(source, tmp_path / "store-root", write_parquet=True)
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(request)

    assert materializer.last_manifest_path is not None
    manifest_path = materializer.last_manifest_path
    payload = json.loads(manifest_path.read_text())
    payload["schema_version"] = "1.0"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="schema is stale"):
        materializer.materialize(request)


def test_parquet_payload_validation_rejects_unreadable_row_group(tmp_path: Path) -> None:
    path = tmp_path / "part.parquet"
    path.write_bytes(b"placeholder")

    class _Reader:
        metadata = SimpleNamespace(num_row_groups=1)

        def read_row_group(self, row_group: int) -> None:
            del row_group
            raise OSError("ZSTD decompression failed: Data corruption detected")

    module = SimpleNamespace(ParquetFile=lambda candidate: _Reader())
    with pytest.raises(ValueError, match=r"row group 0"):
        validate_parquet_payloads((path,), parquet=module)


def test_bounded_materialization_publishes_explicit_partial_status(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        manifest = materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "store-root",
                write_parquet=True,
                max_cus=1,
            )
        )

    assert manifest.status == "partial"
    assert manifest.configuration["max_cus"] == 1
    assert materializer.last_manifest_path is not None
    projection_payload = json.loads(
        (materializer.last_manifest_path.parent / "parquet" / "manifest.json").read_text()
    )
    assert projection_payload["status"] == "partial"
    with pytest.raises(ValueError, match="not complete"):
        load_analytical_store(materializer.last_manifest_path)
    store = load_analytical_store(materializer.last_manifest_path, allow_incomplete=True)
    assert store.get_compilation_unit(0).status.value == "partial"


def test_jsonl_and_parquet_stores_generate_byte_identical_headers(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "jsonl-store",
                write_jsonl=True,
                write_parquet=False,
            )
        )
        jsonl_manifest = materializer.last_manifest_path
        materializer.materialize(
            DwarfMaterializationRequest(source, tmp_path / "parquet-store", write_parquet=True)
        )
        parquet_manifest = materializer.last_manifest_path

    assert jsonl_manifest is not None
    assert parquet_manifest is not None

    def generate(manifest: Path, cache_file: Path) -> str:
        with DwarfGenerator(
            source,
            session_factory=lambda _path: AnalyticalDwarfSession(
                manifest,
                expected_source_path=source,
            ),
            cache_file=cache_file,
        ) as generator:
            return generator.generate("Thing")

    jsonl_header = generate(jsonl_manifest, tmp_path / "jsonl-cache.json")
    parquet_header = generate(parquet_manifest, tmp_path / "parquet-cache.json")

    assert jsonl_header == parquet_header


def test_jsonl_and_parquet_query_contracts_have_equal_ordered_results(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "jsonl-store",
                write_jsonl=True,
                write_parquet=False,
            )
        )
        jsonl_path = materializer.last_manifest_path
        materializer.materialize(
            DwarfMaterializationRequest(source, tmp_path / "parquet-store", write_parquet=True)
        )
        parquet_path = materializer.last_manifest_path

    assert jsonl_path is not None
    assert parquet_path is not None
    jsonl_store = JsonlDwarfStore.load(jsonl_path)
    parquet_store = ParquetDwarfStore.load(parquet_path)
    operations = (
        lambda store: store.find_definitions("Thing"),
        lambda store: store.get_compilation_unit(0),
        lambda store: store.get_die(0x20),
        lambda store: store.children(0x20),
        lambda store: store.parent(0x20),
        lambda store: store.references(0x20),
    )
    for operation in operations:
        left = operation(jsonl_store)
        right = operation(parquet_store)
        assert left.status is right.status
        assert [_item_signature(item) for item in left.items] == [
            _item_signature(item) for item in right.items
        ]


def _item_signature(item: object) -> object:
    offset = getattr(item, "offset", None)
    if isinstance(offset, int):
        cu = getattr(item, "cu", None)
        return (
            "die",
            offset,
            getattr(cu, "cu_offset", None),
            getattr(item, "tag", None),
            item.get_full_path(),
        )
    if isinstance(item, dict):
        return json.dumps(item, ensure_ascii=True, sort_keys=True, default=str)
    if hasattr(item, "cu_offset"):
        return ("unit", item.cu_offset, getattr(item, "header", {}))
    return repr(item)

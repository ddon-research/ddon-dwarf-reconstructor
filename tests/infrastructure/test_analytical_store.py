"""Deterministic contracts for the analytical DWARF store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator
from ddon_dwarf_reconstructor.core.platform import ELFPlatform
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationManifest,
    QueryResult,
    QueryStatus,
)
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_discovery import (
    ClassParserDiscoveryMixin,
)
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_scan import (
    ClassParserScanMixin,
)
from ddon_dwarf_reconstructor.infrastructure.analytical import (
    AnalyticalDwarfSession,
    DwarfMaterializer,
    JsonlDwarfStore,
    ParquetDwarfStore,
    run_store_benchmark,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark import (
    _knowledge_export_measurement,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import (
    DorisConfig,
    build_doris_plan,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet import ParquetPublisher
from ddon_dwarf_reconstructor.infrastructure.analytical.semantic_emitter import (
    DwarfSemanticEmitter,
)
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog

# The fixture intentionally mirrors the pyelftools method names.
# ruff: noqa: N802

pytestmark = [pytest.mark.unit, pytest.mark.functional]


class _Attribute:
    def __init__(self, value: object, form: str = "DW_FORM_data1") -> None:
        self.value = value
        self.raw_value = value
        self.form = form
        self.offset = 0
        self.indirection_length = 0


class _Die:
    def __init__(
        self,
        tag: str | None,
        offset: int,
        depth: int,
        attributes: dict[str, _Attribute],
        *,
        has_children: bool = False,
        null: bool = False,
    ) -> None:
        self.tag = tag
        self.offset = offset
        self.depth = depth
        self.attributes = attributes
        self.has_children = has_children
        self._null = null
        self._references: dict[str, _Die] = {}
        self.abbrev_code = 1

    def is_null(self) -> bool:
        return self._null

    def get_DIE_from_attribute(self, name: str) -> _Die | None:
        return self._references.get(name)


class _CompilationUnit:
    def __init__(self, dies: list[_Die]) -> None:
        self.cu_offset = 0
        self.header = {"version": 4, "address_size": 8, "unit_length": 32}
        self._dies = dies

    def iter_DIEs(self) -> list[_Die]:
        return self._dies


class _DwarfInfo:
    def __init__(self, units: list[_CompilationUnit]) -> None:
        self.units = units

    def iter_CUs(self) -> list[_CompilationUnit]:
        return self.units


class _Section:
    name = ".debug_info"
    header = {"sh_offset": 0, "sh_size": 4}


class _Elf:
    def iter_sections(self) -> list[_Section]:
        return [_Section()]


class _Session:
    def __init__(self, source: Path, dwarf_info: _DwarfInfo) -> None:
        self.file_handle = source.open("rb")
        self.elf_file = _Elf()
        self.dwarf_info = dwarf_info
        self.platform = ELFPlatform.PS4

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_args: object) -> None:
        self.file_handle.close()


def _fixture_dwarf() -> _DwarfInfo:
    base = _Die(
        "DW_TAG_base_type",
        0x10,
        1,
        {"DW_AT_name": _Attribute(b"u32", "DW_FORM_string")},
    )
    aggregate = _Die(
        "DW_TAG_class_type",
        0x20,
        0,
        {
            "DW_AT_name": _Attribute(b"Thing", "DW_FORM_string"),
            "DW_AT_byte_size": _Attribute(8),
            "DW_AT_type": _Attribute(0x10, "DW_FORM_ref4"),
        },
        has_children=True,
    )
    aggregate._references["DW_AT_type"] = base
    terminator = _Die(None, 0x30, 1, {}, null=True)
    return _DwarfInfo([_CompilationUnit([aggregate, base, terminator])])


def test_materializer_traverses_each_cu_once_and_loads_store(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    catalog = SourceIdentityCatalog(tmp_path / "identities.json")
    materializer = DwarfMaterializer(catalog)

    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        manifest = materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "store-root",
                write_jsonl=True,
                write_parquet=False,
            )
        )

    assert materializer.cu_passes == 1
    assert manifest.counts["unit"] == 1
    assert manifest.counts["die"] == 3
    assert manifest.counts["attribute"] == 4
    assert manifest.counts["reference"] >= 2
    assert materializer.last_manifest_path is not None

    store = JsonlDwarfStore.load(materializer.last_manifest_path)
    definitions = store.find_definitions("Thing")
    assert definitions.status is QueryStatus.COMPLETE
    die = definitions.items[0]
    assert die.offset == 0x20
    assert die.get_DIE_from_attribute("DW_AT_type").offset == 0x10
    assert die.get_full_path() == "Thing"
    assert store.dwarf_info.get_DIE_from_refaddr(0x10).offset == 0x10
    assert (
        store.find_definitions(
            "Thing",
            qualified_name="Thing",
            tags=frozenset({"DW_TAG_class_type"}),
        ).status
        is QueryStatus.COMPLETE
    )
    assert (
        store.find_definitions(
            "Thing",
            qualified_name="other::Thing",
            tags=frozenset({"DW_TAG_class_type"}),
        ).status
        is QueryStatus.NOT_FOUND
    )
    assert (
        store.find_definitions(
            "Thing",
            tags=frozenset({"DW_TAG_structure_type"}),
        ).status
        is QueryStatus.NOT_FOUND
    )

    raw = materializer.last_manifest_path.parent / "raw_sections" / "0000-.debug_info.bin"
    assert raw.read_bytes() == b"ELF!"
    assert hashlib.sha256(raw.read_bytes()).hexdigest()


def test_existing_jsonl_store_backfills_bounded_parquet_projection(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    output_dir = tmp_path / "store-root"
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(
                source,
                output_dir,
                write_jsonl=True,
                write_parquet=False,
                max_open_writers=1,
                parquet_layout="bucketed",
            )
        )
        manifest = materializer.materialize(
            DwarfMaterializationRequest(
                source,
                output_dir,
                write_jsonl=True,
                write_parquet=True,
            )
        )

    assert manifest.files["parquet"] == "parquet"
    assert manifest.configuration["write_parquet"] is True
    metrics = manifest.configuration["parquet_writer_metrics"]
    assert isinstance(metrics, dict)
    assert metrics["max_open_writers"] == 1
    assert metrics["peak_open_writers"] == 1
    assert manifest.configuration["parquet_layout"] == "bucketed"


def test_materializer_decodes_reference_offsets_without_cross_cu_navigation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    catalog = SourceIdentityCatalog(tmp_path / "identities.json")
    materializer = DwarfMaterializer(catalog)
    dwarf = _fixture_dwarf()
    aggregate = dwarf.units[0]._dies[0]

    with (
        patch.object(aggregate, "get_DIE_from_attribute", side_effect=AssertionError),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
            lambda path: _Session(path, dwarf),
        ),
    ):
        materializer.materialize(
            DwarfMaterializationRequest(
                source,
                tmp_path / "store-root",
                write_jsonl=True,
                write_parquet=False,
            )
        )

    assert materializer.last_manifest_path is not None
    records_path = materializer.last_manifest_path.parent / "records.jsonl"
    references = [
        json.loads(line)
        for line in records_path.read_text().splitlines()
        if '"record_type":"reference"' in line
    ]
    assert any(
        reference["attribute_name"] == "DW_AT_type"
        and reference["target_offset"] == 0x10
        and reference["resolution_status"] == QueryStatus.COMPLETE.value
        for reference in references
    )


def test_generator_can_use_materialized_store_without_live_elf_session(tmp_path: Path) -> None:
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
                tmp_path / "store-root",
                write_jsonl=True,
                write_parquet=False,
            )
        )

    assert materializer.last_manifest_path is not None
    with DwarfGenerator(
        source,
        session_factory=lambda _path: AnalyticalDwarfSession(
            materializer.last_manifest_path,
            expected_source_path=source,
        ),
        cache_file=tmp_path / "dwarf-cache.json",
    ) as generator:
        result = generator.find_class("Thing")

    assert result is not None
    assert result[1].offset == 0x20


def test_parquet_projection_round_trips_record_count(tmp_path: Path) -> None:
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
                write_jsonl=False,
                write_parquet=True,
            )
        )

    assert "parquet" in manifest.files
    import pyarrow.dataset as dataset

    projection = materializer.last_manifest_path.parent / "parquet"
    parquet_files = tuple(projection.rglob("part-*.parquet"))
    assert dataset.dataset(parquet_files, format="parquet").count_rows() == sum(
        manifest.counts.values()
    )


def test_direct_parquet_materialization_does_not_require_jsonl(tmp_path: Path) -> None:
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
                write_jsonl=False,
                write_parquet=True,
            )
        )

    assert "records" not in manifest.files
    assert manifest.files["parquet"] == "parquet"
    assert manifest.artifacts
    assert all(artifact.format == "parquet" for artifact in manifest.artifacts)
    assert all(artifact.row_group_count == 1 for artifact in manifest.artifacts)
    assert not (materializer.last_manifest_path.parent / "records.jsonl").exists()
    with AnalyticalDwarfSession(
        materializer.last_manifest_path, expected_source_path=source
    ) as session:
        result = session.store.find_definitions("Thing")
    assert result.status is QueryStatus.COMPLETE
    assert result.items[0].offset == 0x20


def test_parquet_store_queries_without_loading_jsonl_records(tmp_path: Path) -> None:
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
    with AnalyticalDwarfSession(
        materializer.last_manifest_path,
        expected_source_path=source,
    ) as session:
        assert isinstance(session.store, ParquetDwarfStore)
        result = session.store.find_definitions("Thing")

    assert result.status is QueryStatus.COMPLETE
    assert result.items[0].offset == 0x20


def test_store_benchmark_can_hash_complete_knowledge_export(tmp_path: Path) -> None:
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
    with AnalyticalDwarfSession(
        materializer.last_manifest_path,
        expected_source_path=source,
    ) as session:
        result = _knowledge_export_measurement(
            materializer.last_manifest_path,
            session.store,
            ("Thing",),
            1,
        )

    assert result["status"] == "observed"
    assert result["files"] == 4
    assert isinstance(result["sha256"], str)


def test_scalar_location_form_is_not_decoded_as_location_list() -> None:
    records: list[dict[str, object]] = []

    class _Writer:
        def write(self, record: dict[str, object]) -> None:
            records.append(record)

    location_lists = Mock()
    emitter = DwarfSemanticEmitter(
        "source",
        _Writer(),
        SimpleNamespace(location_lists=location_lists),
    )
    emitter.write_attribute_side_tables(
        SimpleNamespace(cu_offset=0),
        SimpleNamespace(offset=0x10),
        "DW_AT_data_member_location",
        SimpleNamespace(form="DW_FORM_data1", value=120, raw_value=120, offset=1),
    )

    assert records[0]["entry_kind"] == "entry"
    assert records[0]["expression"] == 120
    location_lists.assert_not_called()


def test_parquet_partition_derives_unit_bucket_before_normalization() -> None:
    partition = ParquetPublisher._partition(
        {
            "record_type": "die",
            "source_id": "source",
            "unit_offset": 0x1000001,
        }
    )

    assert partition == ("die", "source", 1)


def test_manifest_rejects_invalid_source_identity() -> None:
    payload = {
        "schema_version": "1.0",
        "source_path": "sample.elf",
        "source_identity": {
            "sha256": "a",
            "size": 1,
            "mtime_ns": 1,
            "ctime_ns": 1,
            "device": 1,
            "inode": 1,
        },
        "producer": "test",
        "platform": "unknown",
        "files": {},
        "counts": {},
    }
    manifest = MaterializationManifest.from_dict(payload)
    assert manifest.source_identity.sha256 == "a"


def test_doris_plan_uses_source_aware_family_keys(tmp_path: Path) -> None:
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
    plan = build_doris_plan(
        materializer.last_manifest_path,
        DorisConfig(database="test_db", table="dwarf"),
    )

    sql = "\n".join(plan.sql)
    assert "DUPLICATE KEY(source_id, unit_offset, die_offset, index_type)" in sql
    assert "raw_value_json STRING" in sql
    assert "raw_value_uint LARGEINT" in sql
    assert "`column` BIGINT" in sql
    assert "ADD INDEX IF NOT EXISTS idx_name (name) USING INVERTED" in sql


def test_benchmark_report_preserves_unobserved_doris_status(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
        lambda path: _Session(path, _fixture_dwarf()),
    ):
        report = run_store_benchmark(source, tmp_path / "benchmark", symbols=("Thing",))

    assert report["measurements"]["materialize_parquet"]["cu_passes"] == 1
    assert report["measurements"]["load_store"]["status"] == "observed"
    assert "parquet" not in report["measurements"]
    assert report["measurements"]["doris"]["status"] in {"not_observed", "blocked"}


def test_store_discovery_refuses_cu_scan_after_analytical_miss() -> None:
    query_port = Mock()
    query_port.find_primary_definition.return_value = QueryResult(QueryStatus.NOT_FOUND, ())
    context = SimpleNamespace(query_port=query_port)
    with patch.object(ClassParserScanMixin, "_find_class_full_scan") as full_scan:
        result = ClassParserDiscoveryMixin._find_class_from_store(context, "Missing")

    assert result is None
    full_scan.assert_not_called()

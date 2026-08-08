"""Deterministic checkpoint publication and partial-query contracts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.core.platform import ELFPlatform
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationManifest,
    QueryStatus,
)
from ddon_dwarf_reconstructor.infrastructure.analytical import (
    DwarfMaterializer,
    load_analytical_store,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark import run_store_benchmark
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import build_doris_plan
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet import (
    DERIVED_ROW_GROUP_MAX_ROWS,
    FACT_ROW_GROUP_MAX_ROWS,
    ParquetPublisher,
    ParquetRecordSink,
    _estimate_row_bytes,
    _should_flush,
    describe_parquet_files,
)
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog

pytestmark = [pytest.mark.unit, pytest.mark.functional]
# The fixture intentionally mirrors the pyelftools method names.
# ruff: noqa: N802


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


def _unit_record(source_id: str, unit_offset: int) -> dict[str, object]:
    return {
        "record_type": "unit",
        "source_id": source_id,
        "unit_offset": unit_offset,
        "unit_length": 32,
        "unit_type": None,
        "header": {"version": 4},
    }


def _checkpoint_manifest(
    root: Path,
    source: Path,
    files: tuple[str, ...],
) -> Path:
    identity = SourceIdentityCatalog(root / "identities.json").identify(source)
    manifest = MaterializationManifest(
        schema_version="1.0",
        source_path=str(source),
        source_identity=identity,
        producer="pyelftools-0.33-one-pass-checkpoint",
        platform="ps4",
        files={
            "raw_sections": "raw_sections",
            "raw_values": "raw_values",
            "parquet": "parquet",
            "manifest": "checkpoint.json",
        },
        counts={"unit": 1},
        configuration={
            "cu_passes": 1,
            "parquet_files": list(files),
            "checkpoint": {"status": "in_progress", "cu_count": 1},
        },
        artifacts=describe_parquet_files(root, tuple(root / file for file in files)),
        status="in_progress",
    )
    path = root / "checkpoint.json"
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    return path


def test_row_group_progress_estimate_does_not_encode_scalar_values() -> None:
    """The flush heuristic must remain constant-time over normalized columns."""

    class _ExplodingString(str):
        def encode(self, *_args: object, **_kwargs: object) -> bytes:
            raise AssertionError("row progress estimation must not encode values")

    assert _estimate_row_bytes({"value": _ExplodingString("large text")}) == 64


def test_row_group_flush_has_a_native_arrow_row_cap() -> None:
    """Low estimates must not let a pyarrow conversion grow without bound."""
    assert not _should_flush("attribute", [{}] * (FACT_ROW_GROUP_MAX_ROWS - 1), 0)
    assert _should_flush("attribute", [{}] * FACT_ROW_GROUP_MAX_ROWS, 0)
    assert not _should_flush("index", [{}] * (DERIVED_ROW_GROUP_MAX_ROWS - 1), 0)
    assert _should_flush("index", [{}] * DERIVED_ROW_GROUP_MAX_ROWS, 0)


def test_checkpoint_rotates_parts_and_freezes_file_list(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    (root / "raw_sections").mkdir(parents=True)
    (root / "raw_values").mkdir(parents=True)
    sink = ParquetRecordSink(root)

    sink.write(_unit_record(identity.sha256, 0))
    first_files = sink.checkpoint()
    projection_manifest = json.loads((root / "parquet" / "manifest.json").read_text())
    assert projection_manifest["status"] == "in_progress"
    assert len(projection_manifest["files"]) == len(first_files)
    checkpoint = _checkpoint_manifest(root, source, first_files)
    sink.write(_unit_record(identity.sha256, 0x100))
    sink.close()

    assert len(first_files) == 1
    assert len(sink.snapshot_files()) == 2
    store = load_analytical_store(checkpoint, allow_incomplete=True)
    assert store.unit_count == 1
    assert store.get_compilation_unit(0).status is QueryStatus.PARTIAL
    assert store.get_compilation_unit(0x100).status is QueryStatus.PARTIAL
    with pytest.raises(ValueError, match="not complete"):
        load_analytical_store(checkpoint)
    with pytest.raises(ValueError, match="requires a complete analytical store"):
        build_doris_plan(checkpoint)


def test_parquet_sink_bounds_open_writers_and_preserves_footers(tmp_path: Path) -> None:
    import pyarrow.parquet as parquet

    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    sink = ParquetRecordSink(root, max_open_writers=1, layout="bucketed")

    for unit_offset in (0, 0x1000000, 0x2000000):
        sink.write(_unit_record(identity.sha256, unit_offset))
    sink.close()

    files = tuple(root.rglob("part-*.parquet"))
    assert len(files) == 3
    assert all(parquet.ParquetFile(path).metadata.num_rows == 1 for path in files)
    assert sink.writer_metrics() == {
        "max_open_writers": 1,
        "peak_open_writers": 1,
        "automatic_rotations": 2,
        "checkpoint_rotations": 0,
        "cu_boundary_rotations": 0,
    }


def test_jsonl_backfill_uses_manifest_layout_and_writer_bound(tmp_path: Path) -> None:
    import pyarrow.parquet as parquet

    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    records = root / "records.jsonl"
    root.mkdir()
    records.write_text(
        "".join(
            json.dumps(_unit_record(identity.sha256, offset), sort_keys=True) + "\n"
            for offset in (0, 0x1000000, 0x2000000)
        ),
        encoding="utf-8",
    )
    manifest = MaterializationManifest(
        schema_version="1.1",
        source_path=str(source),
        source_identity=identity,
        producer="test",
        platform="ps4",
        files={"records": "records.jsonl", "parquet": "parquet", "manifest": "manifest.json"},
        counts={"unit": 3},
        configuration={"max_open_writers": 1, "parquet_layout": "bucketed"},
    )

    publisher = ParquetPublisher()
    publisher._publish_at_root(manifest, root)

    files = tuple(sorted((root / "parquet").rglob("part-*.parquet")))
    assert len(files) == 3
    assert all(parquet.ParquetFile(path).metadata.num_rows == 1 for path in files)
    projection = json.loads((root / "parquet" / "manifest.json").read_text())
    assert projection["layout"] == "bucketed"
    assert projection["writer_metrics"]["max_open_writers"] == 1
    assert projection["writer_metrics"]["peak_open_writers"] == 1
    assert projection["writer_metrics"]["automatic_rotations"] == 2


def test_family_layout_retains_unit_bucket_as_a_physical_column(tmp_path: Path) -> None:
    import pyarrow.parquet as parquet

    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    sink = ParquetRecordSink(root, layout="family")

    sink.write(_unit_record(identity.sha256, 0))
    sink.write(_unit_record(identity.sha256, 0x1000000))
    sink.close()

    files = tuple(root.rglob("part-*.parquet"))
    assert len(files) == 1
    assert "unit_bucket=" not in files[0].as_posix()
    assert parquet.read_table(files[0], columns=["unit_bucket"]).column(
        "unit_bucket"
    ).to_pylist() == [0, 1]


def test_family_sink_rotates_closed_files_at_a_cu_boundary(tmp_path: Path) -> None:
    import pyarrow.parquet as parquet

    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    sink = ParquetRecordSink(root, layout="family")

    sink.write(_unit_record(identity.sha256, 0))
    sink.rotate()
    sink.write(_unit_record(identity.sha256, 0x100))
    sink.close()

    files = tuple(sorted(root.rglob("part-*.parquet")))
    assert len(files) == 2
    assert [parquet.ParquetFile(path).metadata.num_rows for path in files] == [1, 1]
    assert sink.writer_metrics()["cu_boundary_rotations"] == 1


def test_materialization_request_exposes_safe_writer_bound() -> None:
    request = DwarfMaterializationRequest(Path("sample.elf"), Path("store"))

    assert request.max_open_writers == 16
    assert request.parquet_layout == "family"
    assert request.rotate_writers_every_cus == 64

    with pytest.raises(ValueError, match="max_open_writers must be positive"):
        DwarfMaterializationRequest(Path("sample.elf"), Path("store"), max_open_writers=0)

    with pytest.raises(ValueError, match="parquet_layout"):
        DwarfMaterializationRequest(Path("sample.elf"), Path("store"), parquet_layout="invalid")

    with pytest.raises(ValueError, match="rotate_writers_every_cus"):
        DwarfMaterializationRequest(Path("sample.elf"), Path("store"), rotate_writers_every_cus=-1)


def test_partial_checkpoint_benchmark_reads_only_committed_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    identity = SourceIdentityCatalog(tmp_path / "identities.json").identify(source)
    root = tmp_path / "store"
    (root / "raw_sections").mkdir(parents=True)
    (root / "raw_values").mkdir(parents=True)
    sink = ParquetRecordSink(root)

    sink.write(_unit_record(identity.sha256, 0))
    committed = sink.checkpoint()
    checkpoint = _checkpoint_manifest(root, source, committed)
    sink.write(_unit_record(identity.sha256, 0x100))
    sink.close()

    report = run_store_benchmark(
        source,
        tmp_path / "benchmark",
        store_manifest=checkpoint,
        symbols=("Thing",),
        iterations=1,
        allow_incomplete=True,
    )

    assert report["status"] == "partial"
    assert report["measurements"]["load_store"]["status"] == "partial"
    assert "parquet" not in report["measurements"]
    assert report["measurements"]["doris"]["status"] == "not_observed"


def test_checkpoint_request_requires_parquet_projection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires the Parquet projection"):
        DwarfMaterializationRequest(
            tmp_path / "sample.elf",
            tmp_path / "store",
            write_jsonl=True,
            write_parquet=False,
            checkpoint_every_cus=1,
        )


def test_interrupted_checkpoint_is_preserved_for_explicit_inspection(tmp_path: Path) -> None:
    source = tmp_path / "sample.elf"
    source.write_bytes(b"ELF!")
    dwarf = _fixture_dwarf()

    class _FailingDwarf:
        def iter_CUs(self):  # noqa: N802
            yield from dwarf.iter_CUs()
            raise RuntimeError("synthetic interruption")

    class _FailingSession(_Session):
        def __init__(self, path: Path) -> None:
            super().__init__(path, _FailingDwarf())
            self.platform = ELFPlatform.PS4

    output = tmp_path / "stores"
    materializer = DwarfMaterializer(SourceIdentityCatalog(tmp_path / "identities.json"))
    request = DwarfMaterializationRequest(
        source,
        output,
        write_parquet=True,
        checkpoint_every_cus=1,
    )
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.materializer.ElfDwarfSession",
            lambda path: _FailingSession(path),
        ),
        pytest.raises(RuntimeError, match="synthetic interruption"),
    ):
        materializer.materialize(request)

    checkpoint_paths = list(output.glob(".*/checkpoint.json"))
    assert len(checkpoint_paths) == 1
    checkpoint_payload = json.loads(checkpoint_paths[0].read_text())
    assert checkpoint_payload["artifacts"]
    store = load_analytical_store(checkpoint_paths[0], allow_incomplete=True)
    assert store.unit_count == 1
    assert store.get_die(0x20).status is QueryStatus.PARTIAL

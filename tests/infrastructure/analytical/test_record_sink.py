"""Finalization failures must remain abortable and cannot publish completion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    MaterializationArtifact,
)
from ddon_dwarf_reconstructor.infrastructure.analytical import materializer, record_sink
from ddon_dwarf_reconstructor.infrastructure.analytical.dwarf_recovery import DwarfRecoveryReport
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet import ParquetRecordSink
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog

pytestmark = [pytest.mark.unit, pytest.mark.regression]


class RecordingSink:
    def __init__(self, *, close_error: OSError | None = None) -> None:
        self.close_error = close_error
        self.close_calls = 0
        self.abort_calls = 0
        self.rotations = 0
        self.records: list[dict[str, object]] = []
        self.artifacts: tuple[MaterializationArtifact, ...] = ()

    def write(self, record: dict[str, object]) -> None:
        self.records.append(record)

    def close(self) -> None:
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error

    def abort(self) -> None:
        self.abort_calls += 1

    def checkpoint(self) -> tuple[str, ...]:
        return ("parquet/part-0.parquet",)

    def rotate(self) -> None:
        self.rotations += 1

    def writer_metrics(self) -> dict[str, int]:
        return {"peak_open_writers": 1}

    def set_status(self, status: str) -> None:
        raise AssertionError(f"Unexpected publication status: {status}")


def test_failed_sink_close_remains_abortable(tmp_path: Path) -> None:
    failure = OSError("native close failed")
    sink = RecordingSink(close_error=failure)
    writer = record_sink.RecordWriter(tmp_path / "records.jsonl", sink)
    writer.write({"record_type": "unit"})

    with pytest.raises(OSError) as raised:
        writer.close()
    writer.abort()
    writer.abort()

    assert raised.value is failure
    assert sink.close_calls == 1
    assert sink.abort_calls == 1
    assert writer._stream is not None and writer._stream.closed


def test_failed_audit_sync_remains_abortable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = RecordingSink()
    writer = record_sink.RecordWriter(tmp_path / "records.jsonl", sink)
    monkeypatch.setattr(record_sink.os, "fsync", Mock(side_effect=OSError("audit sync failed")))

    with pytest.raises(OSError, match="audit sync failed"):
        writer.close()
    writer.abort()

    assert sink.abort_calls == 1
    assert writer._stream is not None and writer._stream.closed


def test_native_close_failure_propagates_and_retains_writer_for_abort(tmp_path: Path) -> None:
    sink = ParquetRecordSink(tmp_path)
    sink.write({"record_type": "unit", "source_id": "a" * 64, "unit_offset": 0})
    partition = next(iter(sink._writers))
    native = sink._writers[partition]
    wrapped = Mock(wraps=native)
    failure = OSError("native close failed")
    wrapped.close.side_effect = failure
    sink._writers[partition] = wrapped

    try:
        with pytest.raises(OSError, match="native close failed") as raised:
            sink.close()
        assert raised.value is failure
        assert partition in sink._writers
        assert not (tmp_path / "parquet" / "manifest.json").exists()
        wrapped.close.side_effect = None
        sink.abort()
        assert wrapped.close.call_count == 2
        assert not sink._writers
    finally:
        native.close()


def test_typed_sink_delegation_keeps_audit_flush_separate(tmp_path: Path) -> None:
    sink: record_sink.ParquetSink = RecordingSink()
    path = tmp_path / "records.jsonl"
    writer = record_sink.RecordWriter(path, sink)
    writer.write({"record_type": "unit"})
    writer.flush()
    assert path.read_text(encoding="utf-8") == '{"record_type":"unit"}\n'
    assert writer.checkpoint() == ("parquet/part-0.parquet",)
    writer.rotate()
    assert writer.snapshot_artifacts() == ()
    assert writer.writer_metrics() == {"peak_open_writers": 1}
    writer.close()
    writer.close()
    writer.abort()
    assert sink.close_calls == 1
    assert sink.abort_calls == 0
    assert sink.rotations == 1


@pytest.mark.parametrize("operation", ["write", "flush", "checkpoint", "rotate"])
def test_closed_record_writer_rejects_further_work(operation: str) -> None:
    writer = record_sink.RecordWriter(None)
    writer.close()
    with pytest.raises(RuntimeError, match="closed record writer"):
        if operation == "write":
            writer.write({"record_type": "unit"})
        else:
            getattr(writer, operation)()


def test_audit_only_lifecycle_has_no_analytical_artifacts(tmp_path: Path) -> None:
    writer = record_sink.RecordWriter(tmp_path / "records.jsonl")
    writer.write({"record_type": "unit"})
    assert writer.checkpoint() == ()
    assert writer.snapshot_artifacts() == ()
    assert writer.writer_metrics() == {}
    writer.rotate()
    writer.close()


@pytest.mark.parametrize("operation", ["close", "checkpoint", "rotate"])
def test_lost_records_prevent_closed_projection_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    sink = ParquetRecordSink(tmp_path)
    sink.write({"record_type": "unit", "source_id": "a" * 64, "unit_offset": 0})
    monkeypatch.setattr(sink, "_refresh_artifacts", lambda: None)
    try:
        with pytest.raises(ValueError, match="Closed Parquet row counts"):
            getattr(sink, operation)()
        assert not (tmp_path / "parquet" / "manifest.json").exists()
    finally:
        sink.abort()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_materializer_aborts_failed_finalization_before_manifest_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cleanup_fails: bool
) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"fixture")
    catalog = SourceIdentityCatalog(tmp_path / "catalog.json")
    producer = materializer.DwarfMaterializer(catalog)
    sink = RecordingSink(close_error=OSError("finalization failed"))
    cleanup_error = OSError("abort failed")
    if cleanup_fails:

        def fail_abort() -> None:
            sink.abort_calls += 1
            raise cleanup_error

        monkeypatch.setattr(sink, "abort", fail_abort)
    monkeypatch.setattr(materializer, "_parquet_sink", lambda _request, _root: sink)
    monkeypatch.setattr(
        producer, "_produce", Mock(return_value=("ps4", [], 0, Mock(spec=DwarfRecoveryReport)))
    )
    output = tmp_path / "output"
    request = DwarfMaterializationRequest(source, output, write_jsonl=True)

    with pytest.raises(OSError) as raised:
        producer.materialize(request)

    if cleanup_fails:
        assert raised.value is cleanup_error
        assert raised.value.__cause__ is sink.close_error
    else:
        assert raised.value is sink.close_error
    assert sink.abort_calls == 1
    assert producer.last_manifest_path is None
    assert not tuple(output.iterdir())

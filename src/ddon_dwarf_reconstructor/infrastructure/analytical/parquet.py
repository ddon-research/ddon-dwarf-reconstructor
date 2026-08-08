"""Streaming Arrow/Parquet projection for typed DWARF records."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import MaterializationArtifact, MaterializationManifest
from .manifest import validate_parquet_payloads
from .optional import import_optional
from .parquet_layout import UNIT_BUCKET_SIZE, unit_bucket_for
from .parquet_rows import normalize_record, schema_for

BATCH_ROWS = 4_096
FACT_ROW_GROUP_TARGET_BYTES = 512 * 1024 * 1024
DERIVED_ROW_GROUP_TARGET_BYTES = 128 * 1024 * 1024
# The byte estimate intentionally stays constant-time, so it can under-estimate
# nested DWARF values.  Cap the native ``Table.from_pylist`` input as well; a
# large, low-entropy row group can otherwise grow until pyarrow's Windows
# extension fails before a Parquet footer is written.
FACT_ROW_GROUP_MAX_ROWS = 65_536
DERIVED_ROW_GROUP_MAX_ROWS = 32_768
PARQUET_PART_GLOB = "part-*.parquet"
# Keep enough rows per source/unit bucket to avoid one open Parquet writer per
# small CU while still giving partitioned readers useful pruning.  A full
# corpus touches many unit buckets; leaving every historical bucket open can
# exhaust native Parquet writer resources before any footer is published.
# Keep one family for each normal bucket open while limiting the number of
# native Zstandard/Parquet writer contexts.  The old 64-writer default reached
# 52 simultaneous writers on the full ELF and crashed pyarrow's Windows
# extension before any footer could be published.
DEFAULT_MAX_OPEN_WRITERS = 16
DEFAULT_PARQUET_LAYOUT = "family"


class ParquetPublisher:
    """Write one typed, queryable Parquet table per record family."""

    def __init__(self) -> None:
        self.last_writer_metrics: dict[str, int] = {}

    def publish(self, manifest: MaterializationManifest) -> Path:
        """Publish from a manifest carrying an explicit local store root."""
        store_root = manifest.configuration.get("store_root")
        if not isinstance(store_root, str):
            raise ValueError("Use publish_from_manifest_path for a manifest with relative paths")
        return self._publish_at_root(manifest, Path(store_root))

    def publish_from_manifest_path(self, manifest_path: Path) -> Path:
        """Publish using a manifest path so relative artifact paths are unambiguous."""
        from .manifest import load_manifest

        manifest = load_manifest(manifest_path)
        return self._publish_at_root(manifest, manifest_path.resolve().parent)

    def _publish_at_root(self, manifest: MaterializationManifest, root: Path) -> Path:
        records_path = root / manifest.files["records"]
        target = self._projection_target(root)
        temporary = target.with_name(f".{target.name}.partial")
        temporary.mkdir(parents=True)
        try:
            self.last_writer_metrics = self._write_projection(
                records_path,
                temporary,
                manifest,
            )
            os.replace(temporary, target)
            return target
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @staticmethod
    def _projection_target(root: Path) -> Path:
        target = root / "parquet"
        if target.exists() and not (target / "manifest.json").is_file():
            raise ValueError(f"Refusing to replace incomplete Parquet projection: {target}")
        return target

    def _write_projection(
        self,
        records_path: Path,
        temporary: Path,
        manifest: MaterializationManifest,
    ) -> dict[str, int]:
        max_open_writers, layout = self._projection_settings(manifest)
        sink = ParquetRecordSink(
            temporary,
            max_open_writers=max_open_writers,
            layout=layout,
            target=temporary,
        )
        try:
            with records_path.open(encoding="utf-8") as stream:
                for line in stream:
                    sink.write(json.loads(line))
            sink.close()
            return sink.writer_metrics()
        except BaseException:
            sink.abort()
            raise

    @staticmethod
    def _projection_settings(manifest: MaterializationManifest) -> tuple[int, str]:
        configuration = manifest.configuration
        max_open_writers = configuration.get("max_open_writers", DEFAULT_MAX_OPEN_WRITERS)
        if (
            isinstance(max_open_writers, bool)
            or not isinstance(max_open_writers, int)
            or max_open_writers <= 0
        ):
            raise ValueError("Manifest max_open_writers must be a positive integer")
        layout = configuration.get("parquet_layout", DEFAULT_PARQUET_LAYOUT)
        if not isinstance(layout, str):
            raise ValueError("Manifest parquet_layout must be a string")
        return max_open_writers, layout

    @staticmethod
    def _partition(record: dict[str, Any]) -> tuple[str, str, int]:
        kind = str(record.get("record_type", "unknown"))
        source_id = str(record.get("source_id") or "none")
        unit_offset = record.get("unit_offset")
        unit_bucket = (
            unit_bucket_for(unit_offset)
            if isinstance(unit_offset, int) and unit_offset >= 0
            else record.get("unit_bucket")
        )
        if not isinstance(unit_bucket, int) or unit_bucket < 0:
            unit_bucket = 0
        return kind, source_id, unit_bucket

    def _writer_for_partition(
        self,
        partition: tuple[str, str, int],
        temporary: Path,
        writers: dict[tuple[str, str, int], Any],
        pyarrow: Any,
        parquet: Any,
        part_numbers: dict[tuple[str, str, int], int] | None = None,
        *,
        partitioned: bool = True,
    ) -> Any:
        writer = writers.get(partition)
        if writer is not None:
            return writer
        kind, source_id, unit_bucket = partition
        family_dir = temporary / kind / f"source_id={_partition_value(source_id)}"
        if partitioned:
            family_dir /= f"unit_bucket={unit_bucket}"
        family_dir.mkdir(parents=True, exist_ok=True)
        part_number = (part_numbers or {}).get(partition, 0)
        writer = self._new_writer(
            pyarrow,
            parquet,
            family_dir / f"part-{part_number:05d}.parquet",
            kind,
        )
        writers[partition] = writer
        return writer

    @staticmethod
    def _new_writer(pyarrow: Any, parquet: Any, path: Path, kind: str) -> Any:
        schema = schema_for(pyarrow, kind)
        return parquet.ParquetWriter(
            path,
            schema,
            compression="zstd",
            use_dictionary=["record_type", "tag", "name", "form", "relation"],
        )

    @staticmethod
    def _flush_buffer(pyarrow: Any, writer: Any, rows: list[dict[str, Any]], kind: str) -> None:
        if not rows:
            return
        writer.write_table(
            pyarrow.Table.from_pylist(rows, schema=schema_for(pyarrow, kind)),
            row_group_size=len(rows),
        )
        rows.clear()

    @staticmethod
    def _row(record: dict[str, Any]) -> dict[str, Any]:
        return normalize_record(record)

    @staticmethod
    def _write_projection_manifest(
        root: Path,
        counts: dict[str, int],
        artifacts: tuple[MaterializationArtifact, ...] = (),
        *,
        status: str = "complete",
        layout: str = "bucketed",
        writer_metrics: dict[str, int] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "backend": "parquet",
            "status": status,
            "compression": "zstd",
            "row_group_target_bytes": {
                "fact": FACT_ROW_GROUP_TARGET_BYTES,
                "derived": DERIVED_ROW_GROUP_TARGET_BYTES,
            },
            "row_group_max_rows": {
                "fact": FACT_ROW_GROUP_MAX_ROWS,
                "derived": DERIVED_ROW_GROUP_MAX_ROWS,
            },
            "batch_rows": BATCH_ROWS,
            "partitioning": {
                "source": "source_id",
                "unit_bucket_size": UNIT_BUCKET_SIZE,
            },
            "layout": layout,
            "counts": dict(sorted(counts.items())),
            "files": [artifact.to_dict() for artifact in artifacts],
        }
        if writer_metrics is not None:
            payload["writer_metrics"] = writer_metrics
        with (root / "manifest.json").open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            stream.write("\n")


class ParquetRecordSink:
    """Write normalized Parquet rows during the one-pass CU traversal.

    The sink intentionally shares the projection schema with ``ParquetPublisher``
    so a real corpus can bypass JSONL entirely.  The materializer owns the outer
    temporary store directory and publishes it atomically after this sink closes.
    """

    def __init__(
        self,
        root: Path,
        max_open_writers: int = DEFAULT_MAX_OPEN_WRITERS,
        layout: str = DEFAULT_PARQUET_LAYOUT,
        *,
        target: Path | None = None,
    ) -> None:
        if max_open_writers <= 0:
            raise ValueError("max_open_writers must be positive")
        if layout not in {"family", "bucketed"}:
            raise ValueError("layout must be 'family' or 'bucketed'")
        self.root = root
        self.max_open_writers = max_open_writers
        self.layout = layout
        self.target = target or root / "parquet"
        self.target.mkdir(parents=True, exist_ok=True)
        self._publisher = ParquetPublisher()
        self._pyarrow = import_optional("pyarrow", "analytical")
        self._parquet = import_optional("pyarrow.parquet", "analytical")
        self._writers: dict[tuple[str, str, int], Any] = {}
        self._buffers: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
        self._buffer_bytes: defaultdict[tuple[str, str, int], int] = defaultdict(int)
        self._part_numbers: defaultdict[tuple[str, str, int], int] = defaultdict(int)
        self.counts: defaultdict[str, int] = defaultdict(int)
        self.artifacts: tuple[MaterializationArtifact, ...] = ()
        self._artifact_cache: dict[str, MaterializationArtifact] = {}
        self._peak_open_writers = 0
        self._automatic_rotations = 0
        self._checkpoint_rotations = 0
        self._cu_boundary_rotations = 0
        self._closed = False

    def write(self, record: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("Cannot write to a closed Parquet record sink")
        raw_partition = self._publisher._partition(record)
        partition = (
            raw_partition if self.layout == "bucketed" else (raw_partition[0], raw_partition[1], 0)
        )
        self._ensure_writer_capacity(partition)
        writer = self._publisher._writer_for_partition(
            partition,
            self.target,
            self._writers,
            self._pyarrow,
            self._parquet,
            self._part_numbers,
            partitioned=self.layout == "bucketed",
        )
        self._peak_open_writers = max(self._peak_open_writers, len(self._writers))
        row = self._publisher._row(record)
        self._buffers[partition].append(row)
        self._buffer_bytes[partition] += _estimate_row_bytes(row)
        self.counts[partition[0]] += 1
        if _should_flush(partition[0], self._buffers[partition], self._buffer_bytes[partition]):
            self._publisher._flush_buffer(
                self._pyarrow, writer, self._buffers[partition], partition[0]
            )
            self._buffer_bytes[partition] = 0

    def writer_metrics(self) -> dict[str, int]:
        """Return bounded native-writer metrics for the materialization manifest."""
        return {
            "max_open_writers": self.max_open_writers,
            "peak_open_writers": self._peak_open_writers,
            "automatic_rotations": self._automatic_rotations,
            "checkpoint_rotations": self._checkpoint_rotations,
            "cu_boundary_rotations": self._cu_boundary_rotations,
        }

    def flush(self) -> None:
        """Flush completed Arrow batches without closing partition writers."""
        pass

    def checkpoint(self) -> tuple[str, ...]:
        """Close current files and rotate subsequent writes to new parts."""
        if self._closed:
            raise RuntimeError("Cannot checkpoint a closed Parquet record sink")
        self._close_open_writers(checkpoint=True)
        self._publisher._write_projection_manifest(
            self.target,
            dict(self.counts),
            self.artifacts,
            status="in_progress",
            layout=self.layout,
            writer_metrics=self.writer_metrics(),
        )
        return self.snapshot_files()

    def rotate(self) -> None:
        """Close current family files without publishing an in-progress snapshot."""
        if self._closed:
            raise RuntimeError("Cannot rotate a closed Parquet record sink")
        if self._close_open_writers():
            self._cu_boundary_rotations += 1

    def close(self) -> None:
        if self._closed:
            return
        self._close_open_writers()
        validate_parquet_payloads(
            (self.root / artifact.path for artifact in self.artifacts),
            parquet=self._parquet,
        )
        self._publisher._write_projection_manifest(
            self.target,
            dict(self.counts),
            self.artifacts,
            layout=self.layout,
            writer_metrics=self.writer_metrics(),
        )
        self._closed = True

    def set_status(self, status: str) -> None:
        """Update the projection marker after outer-store status is known."""
        if not self._closed:
            raise RuntimeError("Parquet sink status cannot change before close")
        self._publisher._write_projection_manifest(
            self.target,
            dict(self.counts),
            self.artifacts,
            status=status,
            layout=self.layout,
            writer_metrics=self.writer_metrics(),
        )

    def abort(self) -> None:
        """Close open writers without flushing a failed Arrow batch."""
        if self._closed:
            return
        for writer in self._writers.values():
            with suppress(Exception):
                writer.close()
        self._writers.clear()
        self._closed = True

    def snapshot_files(self) -> tuple[str, ...]:
        """Return closed Parquet files relative to the outer store root."""
        return tuple(
            sorted(
                path.relative_to(self.root).as_posix()
                for path in self.target.rglob(PARQUET_PART_GLOB)
                if path.is_file()
            )
        )

    def _ensure_writer_capacity(self, requested: tuple[str, str, int]) -> None:
        if requested in self._writers or len(self._writers) < self.max_open_writers:
            return
        oldest = next(iter(self._writers))
        self._close_partition(oldest)
        self._automatic_rotations += 1

    def _close_partition(self, partition: tuple[str, str, int]) -> None:
        writer = self._writers[partition]
        self._publisher._flush_buffer(self._pyarrow, writer, self._buffers[partition], partition[0])
        with suppress(Exception):
            writer.close()
        self._writers.pop(partition, None)
        self._part_numbers[partition] += 1
        self._buffer_bytes.pop(partition, None)

    def _close_open_writers(self, *, checkpoint: bool = False) -> int:
        partitions = tuple(self._writers)
        for partition in partitions:
            self._close_partition(partition)
        if checkpoint:
            self._checkpoint_rotations += len(partitions)
        self._buffer_bytes.clear()
        self._refresh_artifacts()
        return len(partitions)

    def _refresh_artifacts(self) -> None:
        for path in sorted(self.target.rglob(PARQUET_PART_GLOB)):
            relative = path.relative_to(self.root).as_posix()
            if relative not in self._artifact_cache:
                self._artifact_cache[relative] = _describe_parquet_file(self.root, path)
        self.artifacts = tuple(self._artifact_cache[key] for key in sorted(self._artifact_cache))


def describe_parquet_files(
    root: Path, files: Iterable[Path] | None = None
) -> tuple[MaterializationArtifact, ...]:
    """Describe closed Parquet files under a store root in stable order."""
    paths = tuple(files) if files is not None else tuple(root.rglob(PARQUET_PART_GLOB))
    return tuple(
        _describe_parquet_file(root, path)
        for path in sorted(paths, key=lambda value: value.resolve().as_posix())
    )


def _describe_parquet_file(root: Path, path: Path) -> MaterializationArtifact:
    parquet = import_optional("pyarrow.parquet", "analytical")
    metadata = parquet.ParquetFile(path).metadata
    row_group_rows = tuple(
        int(metadata.row_group(index).num_rows) for index in range(metadata.num_row_groups)
    )
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return MaterializationArtifact(
        path=relative,
        format="parquet",
        size_bytes=path.stat().st_size,
        sha256=_sha256_file(path),
        modified_ns=path.stat().st_mtime_ns,
        family=relative.split("/", 1)[0],
        compression=_compression(metadata),
        row_group_count=int(metadata.num_row_groups),
        row_group_rows=row_group_rows,
    )


def _compression(metadata: Any) -> str | None:
    values = {
        str(metadata.row_group(index).column(column).compression).lower()
        for index in range(metadata.num_row_groups)
        for column in range(metadata.row_group(index).num_columns)
    }
    if not values:
        return None
    return next(iter(values)) if len(values) == 1 else "mixed"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _partition_value(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "_" for character in value
    )


def _should_flush(kind: str, rows: list[dict[str, Any]], estimated_bytes: int) -> bool:
    if len(rows) < BATCH_ROWS:
        return False
    target = DERIVED_ROW_GROUP_TARGET_BYTES if kind == "index" else FACT_ROW_GROUP_TARGET_BYTES
    max_rows = DERIVED_ROW_GROUP_MAX_ROWS if kind == "index" else FACT_ROW_GROUP_MAX_ROWS
    return estimated_bytes >= target or len(rows) >= max_rows


def _estimate_row_bytes(row: dict[str, Any]) -> int:
    """Estimate row-group progress with constant-time normalized-row metadata.

    This value only controls when an Arrow batch becomes a Parquet row group;
    it is not a storage-size or correctness measurement. Walking every scalar
    and encoding every string made this approximation the dominant producer
    CPU path on the real ELF, so use a stable per-column estimate instead.
    """
    return max(64, len(row) * 64)

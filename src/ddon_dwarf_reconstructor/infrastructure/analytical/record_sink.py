"""Sinks shared by the one-pass analytical record producer."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from ...domain.models.analytical_dwarf import MaterializationArtifact


class ParquetSink(Protocol):
    """Required lifecycle of the materializer's bounded analytical projection."""

    @property
    def artifacts(self) -> tuple[MaterializationArtifact, ...]: ...

    def write(self, record: dict[str, object]) -> None: ...

    def close(self) -> None: ...

    def abort(self) -> None: ...

    def checkpoint(self) -> tuple[str, ...]: ...

    def rotate(self) -> None: ...

    def writer_metrics(self) -> dict[str, int]: ...

    def set_status(self, status: str) -> None: ...


class RecordWriter:
    """Fan out each lossless row to optional audit and Parquet sinks."""

    def __init__(self, path: Path | None, parquet_sink: ParquetSink | None = None) -> None:
        self._stream = path.open("w", encoding="utf-8", newline="\n") if path is not None else None
        self._parquet_sink = parquet_sink
        self._closed = False
        self.counts: Counter[str] = Counter()

    def write(self, record: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("Cannot write to a closed record writer")
        kind = str(record.get("record_type", "unknown"))
        self.counts[kind] += 1
        if self._stream is not None:
            self._stream.write(
                json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            )
            self._stream.write("\n")
        if self._parquet_sink is not None:
            self._parquet_sink.write(record)

    def close(self) -> None:
        if self._closed:
            return
        if self._stream is not None and not self._stream.closed:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
        if self._parquet_sink is not None:
            self._parquet_sink.close()
        self._closed = True

    def abort(self) -> None:
        """Close failed projections without retrying a buffer that already failed."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._stream is not None:
                self._stream.close()
        finally:
            if self._parquet_sink is not None:
                self._parquet_sink.abort()

    def flush(self) -> None:
        """Flush the audit stream; analytical writers remain open."""
        if self._closed:
            raise RuntimeError("Cannot flush a closed record writer")
        if self._stream is not None:
            self._stream.flush()

    def checkpoint(self) -> tuple[str, ...]:
        """Publish a stable Parquet file boundary for an explicit snapshot."""
        if self._closed:
            raise RuntimeError("Cannot checkpoint a closed record writer")
        self.flush()
        if self._parquet_sink is None:
            return ()
        return self._parquet_sink.checkpoint()

    def rotate(self) -> None:
        """Close Parquet writers at a safe CU boundary without publishing a checkpoint."""
        if self._closed:
            raise RuntimeError("Cannot rotate a closed record writer")
        self.flush()
        if self._parquet_sink is not None:
            self._parquet_sink.rotate()

    def snapshot_artifacts(self) -> tuple[MaterializationArtifact, ...]:
        """Return metadata for the sink's last closed file boundary."""
        if self._parquet_sink is None:
            return ()
        return self._parquet_sink.artifacts

    def writer_metrics(self) -> dict[str, int]:
        """Return native analytical-writer metrics when a sink is configured."""
        if self._parquet_sink is None:
            return {}
        return self._parquet_sink.writer_metrics()

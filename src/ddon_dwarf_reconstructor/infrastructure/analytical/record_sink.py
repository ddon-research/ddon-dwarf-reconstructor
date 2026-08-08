"""Sinks shared by the one-pass analytical record producer."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, cast

from ...domain.models.analytical_dwarf import MaterializationArtifact


class RecordWriter:
    """Fan out each lossless row to optional audit and Parquet sinks."""

    def __init__(self, path: Path | None, parquet_sink: Any = None) -> None:
        self._stream = path.open("w", encoding="utf-8", newline="\n") if path is not None else None
        self._parquet_sink = parquet_sink
        self._closed = False
        self.counts: Counter[str] = Counter()

    def write(self, record: dict[str, Any]) -> None:
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
        self._closed = True
        if self._stream is not None:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
        if self._parquet_sink is not None:
            self._parquet_sink.close()

    def abort(self) -> None:
        """Close failed projections without retrying a buffer that already failed."""
        if self._closed:
            return
        self._closed = True
        if self._stream is not None:
            self._stream.close()
        if self._parquet_sink is not None:
            abort = getattr(self._parquet_sink, "abort", None)
            if callable(abort):
                abort()

    def flush(self) -> None:
        """Flush the audit stream; analytical writers remain open."""
        if self._stream is not None:
            self._stream.flush()
        if self._parquet_sink is not None:
            self._parquet_sink.flush()

    def checkpoint(self) -> tuple[str, ...]:
        """Publish a stable Parquet file boundary for an explicit snapshot."""
        if self._closed:
            raise RuntimeError("Cannot checkpoint a closed record writer")
        self.flush()
        if self._parquet_sink is None:
            return ()
        checkpoint = getattr(self._parquet_sink, "checkpoint", None)
        if not callable(checkpoint):
            raise TypeError("Analytical sink does not support checkpoints")
        return cast("tuple[str, ...]", checkpoint())

    def rotate(self) -> None:
        """Close Parquet writers at a safe CU boundary without publishing a checkpoint."""
        if self._closed:
            raise RuntimeError("Cannot rotate a closed record writer")
        self.flush()
        if self._parquet_sink is not None:
            rotate = getattr(self._parquet_sink, "rotate", None)
            if not callable(rotate):
                raise TypeError("Analytical sink does not support writer rotation")
            rotate()

    def snapshot_artifacts(self) -> tuple[MaterializationArtifact, ...]:
        """Return metadata for the sink's last closed file boundary."""
        if self._parquet_sink is None:
            return ()
        artifacts = getattr(self._parquet_sink, "artifacts", ())
        if not isinstance(artifacts, tuple) or not all(
            isinstance(value, MaterializationArtifact) for value in artifacts
        ):
            raise TypeError("Analytical sink returned invalid artifact metadata")
        return artifacts

    def writer_metrics(self) -> dict[str, int]:
        """Return native analytical-writer metrics when the sink exposes them."""
        if self._parquet_sink is None:
            return {}
        metrics = getattr(self._parquet_sink, "writer_metrics", None)
        if not callable(metrics):
            return {}
        value = metrics()
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, int) for key, item in value.items()
        ):
            raise TypeError("Analytical sink returned invalid writer metrics")
        return value

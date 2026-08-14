"""Typed Doris optimization identities and opt-in generation query tracing."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .doris_optimization_utils import (
    int_mapping as _int_mapping,
)
from .doris_optimization_utils import (
    last_query_id as _last_query_id,
)
from .doris_optimization_utils import (
    mapping as _mapping,
)
from .doris_optimization_utils import (
    mapping_sequence as _mapping_sequence,
)
from .doris_optimization_utils import (
    query_shape as _query_shape,
)
from .doris_optimization_utils import (
    sha256_file as _sha256_file,
)
from .doris_optimization_utils import (
    sha256_text as _sha256_text,
)
from .doris_optimization_utils import (
    write_json_atomic as _write_json_atomic,
)


@dataclass(frozen=True, slots=True)
class DorisQueryTraceConfig:
    """Bounded configuration for source-bound generation query tracing."""

    path: Path
    profile_threshold_ms: float = 500.0
    max_profile_instances: int = 20
    profile_timeout_seconds: float = 30.0
    workload: str = "generation"

    def __post_init__(self) -> None:
        if not str(self.path).strip():
            raise ValueError("query trace path must not be empty")
        if self.profile_threshold_ms <= 0:
            raise ValueError("profile_threshold_ms must be positive")
        if self.max_profile_instances < 1:
            raise ValueError("max_profile_instances must be positive")
        if self.profile_timeout_seconds <= 0:
            raise ValueError("profile_timeout_seconds must be positive")
        if not self.workload.strip():
            raise ValueError("query trace workload must not be empty")

    @classmethod
    def from_environment(cls) -> DorisQueryTraceConfig | None:
        """Read the explicit child-process tracing contract, if enabled."""
        path = os.getenv("DDON_DORIS_QUERY_TRACE_PATH")
        if not path:
            return None
        return cls(
            Path(path),
            profile_threshold_ms=float(
                os.getenv("DDON_DORIS_QUERY_TRACE_PROFILE_THRESHOLD_MS", "500")
            ),
            max_profile_instances=int(os.getenv("DDON_DORIS_QUERY_TRACE_MAX_PROFILES", "20")),
            profile_timeout_seconds=float(
                os.getenv("DDON_DORIS_QUERY_TRACE_PROFILE_TIMEOUT_SECONDS", "30")
            ),
            workload=os.getenv("DDON_DORIS_QUERY_TRACE_WORKLOAD", "generation"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path.resolve()),
            "profile_threshold_ms": self.profile_threshold_ms,
            "max_profile_instances": self.max_profile_instances,
            "profile_timeout_seconds": self.profile_timeout_seconds,
            "workload": self.workload,
        }


@dataclass(frozen=True, slots=True)
class DorisQueryObservation:
    """One bounded observation from the actual Doris runtime query boundary."""

    source_id: str
    workload: str
    family: str
    operation: str
    query_shape_sha256: str
    sequence: int
    query_id: str | None
    execute_seconds: float
    fetch_seconds: float
    result_rows: int
    status: str
    profile_status: str
    profile_summary: Mapping[str, object] = field(default_factory=dict)
    engine_metrics: Mapping[str, object] = field(default_factory=dict)
    scan_bytes: int | float | None = None
    scan_rows: int | float | None = None
    tablet_count: int | float | None = None
    schedule_seconds: int | float | None = None
    operator_seconds: int | float | None = None
    peak_memory_bytes: int | float | None = None
    spill_bytes: int | float | None = None
    profile_artifact: Mapping[str, object] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "workload": self.workload,
            "family": self.family,
            "operation": self.operation,
            "query_shape_sha256": self.query_shape_sha256,
            "sequence": self.sequence,
            "query_id": self.query_id,
            "execute_seconds": self.execute_seconds,
            "fetch_seconds": self.fetch_seconds,
            "result_rows": self.result_rows,
            "status": self.status,
            "profile_status": self.profile_status,
            "profile_summary": dict(self.profile_summary),
            "engine_metrics": dict(self.engine_metrics),
            "scan_bytes": self.scan_bytes,
            "scan_rows": self.scan_rows,
            "tablet_count": self.tablet_count,
            "schedule_seconds": self.schedule_seconds,
            "operator_seconds": self.operator_seconds,
            "peak_memory_bytes": self.peak_memory_bytes,
            "spill_bytes": self.spill_bytes,
            "profile_artifact": None
            if self.profile_artifact is None
            else dict(self.profile_artifact),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class DorisOptimizationReport:
    """Typed additive report contract for one Doris optimization evaluation."""

    schema_version: str
    status: str
    workload: str
    variant: Mapping[str, object]
    baseline_identity: Mapping[str, object]
    complete_row_counts: Mapping[str, int]
    load_evidence: Mapping[str, object]
    statistics_evidence: Mapping[str, object]
    tablet_evidence: Mapping[str, object]
    cold_samples: Sequence[Mapping[str, object]]
    warm_samples: Sequence[Mapping[str, object]]
    query_traces: Sequence[Mapping[str, object]]
    output_hashes: Mapping[str, object]
    rejected_optimizations: Sequence[Mapping[str, object]]
    not_applicable_optimizations: Sequence[Mapping[str, object]]
    selected_candidate: Mapping[str, object]
    promotion_gate: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_current_report(
        cls,
        current: Mapping[str, object],
        *,
        selected_candidate: Mapping[str, object],
        matrix: Sequence[Mapping[str, object]],
        promotion_gate: Mapping[str, object],
    ) -> DorisOptimizationReport:
        runs = _mapping_sequence(current.get("runs"))
        validation = _mapping(current.get("serving_validation"))
        statistics_evidence, tablet_evidence = _report_evidence(validation)
        rejected = tuple(item for item in matrix if item.get("category") == "rejected")
        not_applicable = tuple(item for item in matrix if item.get("status") == "not_applicable")
        return cls(
            schema_version="1.0",
            status=str(current.get("status", "not_observed")),
            workload="doris-optimization",
            variant=_mapping(current.get("serving_variant")),
            baseline_identity={
                "source_identity": _mapping(current.get("source_identity")),
                "store_manifest": current.get("store_manifest"),
                "backend": _mapping(current.get("backend")),
            },
            complete_row_counts=_int_mapping(validation.get("observed_counts")),
            load_evidence={
                "status": "not_observed",
                "reason": "optimization benchmark reuses the existing publication",
            },
            statistics_evidence=statistics_evidence,
            tablet_evidence=tablet_evidence,
            cold_samples=_report_samples(runs, "cold"),
            warm_samples=_report_samples(runs, "warm", "long"),
            query_traces=_report_traces(runs),
            output_hashes=_report_output_hashes(runs),
            rejected_optimizations=rejected,
            not_applicable_optimizations=not_applicable,
            selected_candidate=dict(selected_candidate),
            promotion_gate=dict(promotion_gate),
            metadata={
                "workload_configuration": _mapping(current.get("workload_configuration")),
                "bounded_doris_query_contract": _mapping(
                    current.get("bounded_doris_query_contract")
                ),
                "doris_diagnostics": _mapping(current.get("doris_diagnostics")),
            },
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "workload": self.workload,
            "variant": dict(self.variant),
            "baseline_identity": dict(self.baseline_identity),
            "complete_row_counts": dict(self.complete_row_counts),
            "load_evidence": dict(self.load_evidence),
            "statistics_evidence": dict(self.statistics_evidence),
            "tablet_evidence": dict(self.tablet_evidence),
            "cold_samples": [dict(item) for item in self.cold_samples],
            "warm_samples": [dict(item) for item in self.warm_samples],
            "query_traces": [dict(item) for item in self.query_traces],
            "output_hashes": dict(self.output_hashes),
            "rejected_optimizations": [dict(item) for item in self.rejected_optimizations],
            "not_applicable_optimizations": [
                dict(item) for item in self.not_applicable_optimizations
            ],
            "selected_candidate": dict(self.selected_candidate),
            "promotion_gate": dict(self.promotion_gate),
            "metadata": dict(self.metadata),
        }


def _report_evidence(
    validation: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    statistics = _mapping(validation.get("statistics_evidence"))
    tablets = _mapping(validation.get("tablet_evidence"))
    return (
        statistics
        or {
            "status": "not_observed",
            "reason": "statistics capture is an explicit serving evidence step",
        },
        tablets
        or {
            "status": "not_observed",
            "reason": "tablet inspection is an explicit serving evidence step",
        },
    )


def _report_samples(
    runs: Sequence[Mapping[str, object]], *states: str
) -> tuple[Mapping[str, object], ...]:
    return tuple(item for item in runs if item.get("state") in states)


def _report_traces(
    runs: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        trace
        for item in runs
        for trace in (item.get("query_trace"),)
        if isinstance(trace, Mapping) and trace.get("status") != "not_observed"
    )


def _report_output_hashes(
    runs: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        _run_key(item): {
            str(file.get("path")): file.get("sha256")
            for file in _mapping_sequence(_mapping(item.get("output")).get("files"))
            if file.get("sha256") is not None
        }
        for item in runs
        if _mapping_sequence(_mapping(item.get("output")).get("files"))
    }


def _run_key(item: Mapping[str, object]) -> str:
    return (
        f"{item.get('symbol', 'unknown')}:{item.get('state', 'unknown')}:{item.get('iteration', 0)}"
    )


def _observation_status(error: BaseException | None, profile_status: str) -> str:
    if error is not None:
        return "blocked"
    return "partial" if profile_status not in {"observed", "not_observed"} else "observed"


def _metric_number(metrics: Mapping[str, object], name: str) -> int | float | None:
    value = metrics.get(name)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class DorisQueryTracer:
    """Write bounded JSONL query observations and sampled Doris profiles."""

    def __init__(
        self,
        source_id: str,
        config: Any,
        trace_config: DorisQueryTraceConfig,
        profile_fetcher: Callable[
            [str, float],
            tuple[str, Mapping[str, object], Mapping[str, object], object | None, str | None],
        ]
        | None = None,
    ) -> None:
        self.source_id = source_id
        self.config = config
        self.trace_config = trace_config
        self.path = trace_config.path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._summary_path = self.path.with_suffix(".json")
        self._stream = self.path.open("a", encoding="utf-8", newline="\n")
        self._sequence = 0
        self._profile_count = 0
        self._profiled_shapes: set[str] = set()
        self._shape_counts: dict[str, int] = {}
        self._observed = 0
        self._partial = 0
        self._closed = False
        self._profile_fetcher = profile_fetcher

    def record(
        self,
        connection: Any,
        *,
        sql: str,
        family: str,
        operation: str,
        execute_seconds: float,
        fetch_seconds: float,
        rows: Sequence[Sequence[object]],
        error: BaseException | None = None,
    ) -> None:
        """Record one completed or failed DB-API query without parameter values."""
        if self._closed:
            return
        self._sequence += 1
        shape = _query_shape(sql)
        shape_hash = _sha256_text(f"{self.source_id}\0{shape}")
        self._shape_counts[shape_hash] = self._shape_counts.get(shape_hash, 0) + 1
        query_id, query_id_error = _last_query_id(connection)
        profile_status, profile_summary, engine_metrics, profile_artifact, profile_error = (
            self._profile_observation(
                query_id,
                query_id_error,
                shape_hash,
                (execute_seconds + fetch_seconds) * 1000.0,
            )
        )
        status = _observation_status(error, profile_status)
        self._observed += status == "observed"
        self._partial += status != "observed"
        observation = DorisQueryObservation(
            source_id=self.source_id,
            workload=self.trace_config.workload,
            family=family,
            operation=operation,
            query_shape_sha256=shape_hash,
            sequence=self._sequence,
            query_id=query_id,
            execute_seconds=execute_seconds,
            fetch_seconds=fetch_seconds,
            result_rows=len(rows),
            status=status,
            profile_status=profile_status,
            profile_summary=profile_summary,
            engine_metrics=engine_metrics,
            scan_bytes=_metric_number(engine_metrics, "scan_bytes"),
            scan_rows=_metric_number(engine_metrics, "scan_rows"),
            tablet_count=_metric_number(engine_metrics, "tablet_count"),
            schedule_seconds=_metric_number(engine_metrics, "schedule_seconds"),
            operator_seconds=_metric_number(engine_metrics, "operator_seconds"),
            peak_memory_bytes=_metric_number(engine_metrics, "peak_memory_bytes"),
            spill_bytes=_metric_number(engine_metrics, "spill_bytes"),
            profile_artifact=profile_artifact,
            error=str(error or profile_error) if (error or profile_error) else None,
        )
        self._stream.write(json.dumps(observation.to_dict(), sort_keys=True, default=str) + "\n")
        self._stream.flush()

    def _profile_observation(
        self,
        query_id: str | None,
        query_id_error: str | None,
        shape_hash: str,
        elapsed_ms: float,
    ) -> tuple[
        str,
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object] | None,
        str | None,
    ]:
        if query_id is None:
            return "partial", {}, {}, None, query_id_error or "Doris returned no query ID"
        if not self._should_profile(shape_hash, elapsed_ms):
            return "not_observed", {}, {}, None, query_id_error
        return self._capture_profile(query_id, shape_hash)

    def close(self) -> None:
        """Flush the trace and publish its compact summary atomically."""
        if self._closed:
            return
        self._closed = True
        self._stream.flush()
        self._stream.close()
        summary = {
            "schema_version": "1.0",
            "status": "observed" if self._observed and not self._partial else "partial",
            "source_identity": self.source_id,
            "trace": self.trace_config.to_dict(),
            "artifact": {"path": str(self.path), "bytes": self.path.stat().st_size},
            "counts": {
                "query_count": self._sequence,
                "observed_count": self._observed,
                "partial_count": self._partial,
                "profile_count": self._profile_count,
                "shape_count": len(self._shape_counts),
            },
            "shapes": dict(sorted(self._shape_counts.items())),
        }
        _write_json_atomic(self._summary_path, summary)

    def _should_profile(self, shape_hash: str, elapsed_ms: float) -> bool:
        if self._profile_count >= self.trace_config.max_profile_instances:
            return False
        if shape_hash not in self._profiled_shapes:
            return True
        return elapsed_ms >= self.trace_config.profile_threshold_ms

    def _capture_profile(
        self, query_id: str, shape_hash: str
    ) -> tuple[
        str, Mapping[str, object], Mapping[str, object], Mapping[str, object] | None, str | None
    ]:
        if self._profile_fetcher is None:
            return "partial", {}, {}, None, "Doris profile provider is not configured"
        try:
            status, summary, metrics, payload, error = self._profile_fetcher(
                query_id, self.trace_config.profile_timeout_seconds
            )
            if status != "observed" or payload is None:
                return (
                    status,
                    {},
                    {},
                    None,
                    error or "Doris profile was not returned",
                )
            artifact_path = (
                self.path.parent
                / "profiles"
                / f"{self.path.stem}-{shape_hash}-{self._sequence:06d}.json"
            )
            _write_json_atomic(artifact_path, payload)
            self._profile_count += 1
            self._profiled_shapes.add(shape_hash)
            return (
                "observed",
                summary,
                metrics,
                {"path": str(artifact_path), "sha256": _sha256_file(artifact_path)},
                None,
            )
        except (OSError, RuntimeError, ValueError) as error:
            return "partial", {}, {}, None, str(error)


__all__ = [
    "DorisOptimizationReport",
    "DorisQueryObservation",
    "DorisQueryTraceConfig",
    "DorisQueryTracer",
]

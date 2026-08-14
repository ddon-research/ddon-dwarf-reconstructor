"""Blocked and not-observed report construction for Doris candidates."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ...doris_optimization import DorisOptimizationReport
from ...doris_serving_profile import DorisServingProfile


def not_observed_report(
    candidate: Any,
    candidates: Sequence[Any],
    config: Any,
    output_dir: Path,
    reason: str,
    *,
    status: str = "not_observed",
) -> dict[str, object]:
    matrix = [item.to_dict() for item in candidates]
    promotion_gate = {
        "minimum_improvement_percent": 10,
        "maximum_regression_percent": 10,
        "parity_required": True,
    }
    selected = candidate.to_dict()
    typed_report = DorisOptimizationReport(
        schema_version="1.0",
        status=status,
        workload="doris-optimization",
        variant=DorisServingProfile.from_config(
            config, variant_id=candidate.candidate_id
        ).to_dict(),
        baseline_identity={},
        complete_row_counts={},
        load_evidence={"status": "not_observed", "reason": reason},
        statistics_evidence={"status": "not_observed", "reason": reason},
        tablet_evidence={"status": "not_observed", "reason": reason},
        cold_samples=(),
        warm_samples=(),
        query_traces=(),
        output_hashes={},
        rejected_optimizations=tuple(item for item in matrix if item.get("category") == "rejected"),
        not_applicable_optimizations=tuple(
            item for item in matrix if item.get("status") == "not_applicable"
        ),
        selected_candidate=selected,
        promotion_gate=promotion_gate,
        metadata={"matrix": matrix},
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "workload": "doris-optimization",
        "selected_candidate": selected,
        "artifact_root": str(output_dir),
        "reason": reason,
        "optimization": {
            "selected_candidate": selected,
            "matrix": matrix,
            "promotion_gate": promotion_gate,
        },
        "optimization_report": typed_report.to_dict(),
    }

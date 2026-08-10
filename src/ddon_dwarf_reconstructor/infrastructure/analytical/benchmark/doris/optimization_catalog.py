"""Catalog of Doris optimization candidates independent of benchmark execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DorisOptimizationCandidate:
    """One isolated, evidence-gated optimization variant."""

    candidate_id: str
    category: str
    status: str
    reason: str
    settings: dict[str, object]
    table_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "category": self.category,
            "status": self.status,
            "reason": self.reason,
            "settings": dict(self.settings),
            "table_name": self.table_name,
        }


def physical_candidates() -> tuple[DorisOptimizationCandidate, ...]:
    """Return physical and session variants that remain explicit candidates."""
    definitions = (
        ("drop-inverted-index", {"index_change": "remove_one_inverted_index"}),
        ("trim-redundant-bloom", {"index_change": "remove_key_column_bloom"}),
        ("bucket-tiny-one", {"bucket_change": "tiny_families_to_one_bucket"}),
        ("storage-v3-widest", {"storage_format": "V3", "family": "attribute"}),
        ("compression-lz4-widest", {"compression": "lz4", "family": "attribute"}),
        ("pipeline-parallelism", {"parallel_pipeline_task_num": "default,1,higher"}),
        ("sql-cache", {"enable_sql_cache": "off,on"}),
        ("stream-load-workers", {"workers": "1,2,4,8"}),
    )
    return tuple(
        DorisOptimizationCandidate(
            candidate_id,
            "physical-or-runtime",
            "not_observed",
            "Run as an isolated one-factor comparison.",
            dict(settings),
        )
        for candidate_id, settings in definitions
    )


def rejected_candidates() -> tuple[DorisOptimizationCandidate, ...]:
    """Return features rejected or inapplicable for the current workload."""
    return (
        DorisOptimizationCandidate(
            "grouped-child-tag-counts",
            "rejected",
            "rejected",
            "Grouped COUNT(*) reduced result rows but did not improve the warm exhaustive rAIFSM run.",
            {"query": "COUNT(*) GROUP BY parent_offset,tag", "screen": "grouped-paired-20260810"},
        ),
        DorisOptimizationCandidate(
            "row-store",
            "rejected",
            "not_applicable",
            "The workload is append-only analytical Duplicate Key data, not Unique MOW point SELECT *.",
            {"store_row_column": False},
        ),
        DorisOptimizationCandidate(
            "async-materialized-view",
            "rejected",
            "not_applicable",
            "Exact immutable manifest binding is better served by an auxiliary table.",
            {"refresh": "not_promoted"},
        ),
        DorisOptimizationCandidate(
            "group-commit",
            "rejected",
            "not_applicable",
            "The publication is immutable bulk Stream Load rather than frequent small batches.",
            {"group_commit": False},
        ),
        DorisOptimizationCandidate(
            "complex-sql-features",
            "rejected",
            "not_applicable",
            "Current generation trace is single-table parameterized lookup work.",
            {"features": "cte,subquery,lateral,complex,multidimensional,runtime-filter"},
        ),
        DorisOptimizationCandidate(
            "targeted-child-tag-filter",
            "rejected",
            "rejected",
            "Exact filter regressed warm exhaustive rAIFSM despite returning fewer child rows.",
            {
                "child_tag_filter": "targeted",
                "runtime_only": True,
                "screen": "child-tag-filter-screen-20260810",
            },
        ),
    )


__all__ = ["DorisOptimizationCandidate", "physical_candidates", "rejected_candidates"]

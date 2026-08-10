"""Environment overlays for isolated Doris optimization candidates."""

from __future__ import annotations

from ...doris import DorisConfig
from .optimization_catalog import DorisOptimizationCandidate


def candidate_environment(
    config: DorisConfig, candidate: DorisOptimizationCandidate
) -> dict[str, str]:
    """Build the bounded child-process environment for one candidate."""
    environment = {"DDON_DORIS_SERVING_VARIANT_ID": candidate.candidate_id}
    if candidate.candidate_id == "combined-positive-below-gate":
        environment.update(
            {
                "DDON_DORIS_REFERENCE_PREFETCH": "lazy",
                "DDON_DORIS_ATTRIBUTE_PROJECTION": "serving",
                "DDON_DORIS_NAME_LOOKUP_TABLE": f"{config.table}_opt_name_b8",
                "DDON_DORIS_DEFINITION_LOOKUP_TABLE": f"{config.table}_opt_name_b8",
                "DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE": "1",
                "DDON_DORIS_STATISTICS_POLICY": config.statistics_policy,
            }
        )
        return environment
    environment.update(_runtime_policy_environment(candidate))
    if candidate.category != "lookup-table":
        return environment
    environment.update(_lookup_candidate_environment(config, candidate))
    return environment


def _runtime_policy_environment(candidate: DorisOptimizationCandidate) -> dict[str, str]:
    policies = (
        ("reference_prefetch", "DDON_DORIS_REFERENCE_PREFETCH", "lazy"),
        ("attribute_projection", "DDON_DORIS_ATTRIBUTE_PROJECTION", "serving"),
        ("child_tag_filter", "DDON_DORIS_CHILD_TAG_FILTER", "targeted"),
        ("hydration_scope", "DDON_DORIS_HYDRATION_SCOPE", "unit"),
    )
    return {
        environment_name: expected
        for setting_name, environment_name, expected in policies
        if candidate.settings.get(setting_name) == expected
    }


def _lookup_candidate_environment(
    config: DorisConfig, candidate: DorisOptimizationCandidate
) -> dict[str, str]:
    environment: dict[str, str] = {
        "DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE": "1",
        "DDON_DORIS_STATISTICS_POLICY": config.statistics_policy,
    }
    if candidate.candidate_id.startswith("name-lookup-"):
        table = candidate.table_name or ""
        environment["DDON_DORIS_NAME_LOOKUP_TABLE"] = table
        environment["DDON_DORIS_DEFINITION_LOOKUP_TABLE"] = table
    elif candidate.candidate_id == "method-target-b4":
        environment["DDON_DORIS_METHOD_LOOKUP_TABLE"] = candidate.table_name or ""
    elif candidate.candidate_id == "die-offset-b4":
        environment["DDON_DORIS_DIE_LOOKUP_TABLE"] = candidate.table_name or ""
    return environment


__all__ = ["candidate_environment"]

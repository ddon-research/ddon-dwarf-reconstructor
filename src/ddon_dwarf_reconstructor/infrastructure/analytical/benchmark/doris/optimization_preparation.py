"""Candidate preparation and fail-closed provisioning boundaries."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...doris import DorisConfig
from .optimization_catalog import DorisOptimizationCandidate
from .optimization_reports import not_observed_report

ProvisionOne = Callable[[Path, Path, DorisConfig, DorisOptimizationCandidate], dict[str, object]]
ProvisionCombined = Callable[[Path, Path, DorisConfig], dict[str, object]]


def prepare_candidate(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    config: DorisConfig,
    candidates: tuple[DorisOptimizationCandidate, ...],
    selected: DorisOptimizationCandidate,
    provision_requested: bool,
    provision_one: ProvisionOne,
    provision_combined: ProvisionCombined,
) -> tuple[Path, dict[str, object], dict[str, Any] | None]:
    """Prepare an isolated candidate and return any early evidence report."""
    run_output = output_dir / selected.candidate_id
    run_output.mkdir(parents=True, exist_ok=True)
    provisioning: dict[str, object] = {
        "status": "not_observed",
        "reason": "canonical serving projection was reused",
    }
    if selected.candidate_id == "canonical":
        return run_output, provisioning, None
    if selected.candidate_id == "combined-positive-below-gate":
        return _prepare_combined(
            elf,
            store_manifest,
            output_dir,
            config,
            candidates,
            selected,
            run_output,
            provision_requested,
            provision_combined,
        )
    if selected.settings.get("runtime_only") is True:
        return (
            run_output,
            {
                "status": "not_applicable",
                "reason": "runtime-only candidate reuses the canonical source-bound tables",
            },
            None,
        )
    if not provision_requested:
        return _not_observed(
            run_output,
            output_dir,
            candidates,
            selected,
            config,
            "--provision-candidate was not set",
        )
    return _provision_one(
        elf,
        store_manifest,
        output_dir,
        config,
        candidates,
        selected,
        run_output,
        provision_one,
    )


def _prepare_combined(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    config: DorisConfig,
    candidates: tuple[DorisOptimizationCandidate, ...],
    selected: DorisOptimizationCandidate,
    run_output: Path,
    provision_requested: bool,
    provision_combined: ProvisionCombined,
) -> tuple[Path, dict[str, object], dict[str, Any] | None]:
    if not provision_requested:
        return _not_observed(
            run_output,
            output_dir,
            candidates,
            selected,
            config,
            "--provision-candidate was not set",
        )
    try:
        return run_output, provision_combined(elf, store_manifest, config), None
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        report = not_observed_report(
            selected,
            candidates,
            config,
            output_dir,
            f"candidate provisioning was blocked: {error}",
            status="blocked",
        )
        report["provisioning"] = {"status": "blocked", "reason": str(error)}
        return run_output, {"status": "blocked", "reason": str(error)}, report


def _provision_one(
    elf: Path,
    store_manifest: Path,
    output_dir: Path,
    config: DorisConfig,
    candidates: tuple[DorisOptimizationCandidate, ...],
    selected: DorisOptimizationCandidate,
    run_output: Path,
    provision_one: ProvisionOne,
) -> tuple[Path, dict[str, object], dict[str, Any] | None]:
    try:
        return run_output, provision_one(elf, store_manifest, config, selected), None
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        report = not_observed_report(
            selected,
            candidates,
            config,
            output_dir,
            f"candidate provisioning was blocked: {error}",
            status="blocked",
        )
        report["provisioning"] = {"status": "blocked", "reason": str(error)}
        return run_output, {"status": "blocked", "reason": str(error)}, report


def _not_observed(
    run_output: Path,
    output_dir: Path,
    candidates: tuple[DorisOptimizationCandidate, ...],
    selected: DorisOptimizationCandidate,
    config: DorisConfig,
    reason: str,
) -> tuple[Path, dict[str, object], dict[str, Any] | None]:
    return (
        run_output,
        {"status": "not_observed", "reason": reason},
        not_observed_report(selected, candidates, config, output_dir, reason),
    )


__all__ = ["prepare_candidate"]

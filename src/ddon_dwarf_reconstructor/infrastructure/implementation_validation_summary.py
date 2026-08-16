"""Bounded CLI projections for implementation-validation reports."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def implementation_validation_summary(report: Any) -> dict[str, Any]:
    """Project the report without sending its full method evidence to stdout."""
    methods = tuple(report.methods)
    return {
        "schema_version": report.schema_version,
        "validation_profile": report.validation_profile,
        "status": report.status.value,
        "analytical_model": _analytical_model(report),
        "method_count": len(methods),
        "relocation_count": len(report.relocations),
        "nid_count": len(report.nids),
        "compiler_status": report.compiler.status.value,
        "abi_probe_statuses": _status_counts(item.status.value for item in report.abi_probes),
        "method_statuses": _method_statuses(methods),
    }


def _analytical_model(report: Any) -> dict[str, Any] | None:
    model = report.analytical_model
    return model.to_dict() if model is not None else None


def _method_statuses(methods: tuple[Any, ...]) -> dict[str, dict[str, int]]:
    return {
        "relocation": _status_counts(item.relocation_status.value for item in methods),
        "nid": _status_counts(item.nid_status.value for item in methods),
        "abi": _status_counts(item.abi.status.value for item in methods),
        "effects": _status_counts(item.effects.status.value for item in methods),
        "compiler": _status_counts(item.compiler.status.value for item in methods),
        "parity": _status_counts(item.parity.status.value for item in methods),
    }


def _status_counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


__all__ = ["implementation_validation_summary"]

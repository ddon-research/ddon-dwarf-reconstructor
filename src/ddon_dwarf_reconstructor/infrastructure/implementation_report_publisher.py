"""Atomic publication of implementation-validation reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.models.implementation_validation import ImplementationValidationReport
from .artifact_io import atomic_write_text


def write_validation_report(
    report: ImplementationValidationReport,
    output_dir: Path,
) -> ImplementationValidationReport:
    """Publish the validation JSON without exposing a partially written file."""
    target = output_dir / f"implementation-validation-{report.source_sha256[:16]}.json"
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    atomic_write_text(target, payload)
    return report


def read_validation_report(path: Path) -> dict[str, Any]:
    """Read a report and make legacy parity promotion explicitly impossible."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("implementation-validation report must be a JSON object")
    return normalize_validation_report_payload(value)


def normalize_validation_report_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Add the 4.4 static-equivalence default when reading a 4.3 report."""
    normalized = dict(value)
    schema = str(normalized.get("schema_version", "4.3"))
    methods = normalized.get("methods")
    if schema != "4.4" and isinstance(methods, list):
        normalized["methods"] = _legacy_methods(methods)
    return normalized


def _legacy_methods(methods: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for item in methods:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        method = dict(item)
        parity = method.get("parity")
        if isinstance(parity, dict):
            parity = dict(parity)
            parity["static_equivalence"] = "not_promoted"
            method["parity"] = parity
        normalized.append(method)
    return normalized


__all__ = [
    "normalize_validation_report_payload",
    "read_validation_report",
    "write_validation_report",
]

"""Atomic publication of implementation-validation reports."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..domain.models.implementation_validation import ImplementationValidationReport


def write_validation_report(
    report: ImplementationValidationReport,
    output_dir: Path,
) -> ImplementationValidationReport:
    """Publish the validation JSON without exposing a partially written file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"implementation-validation-{report.source_sha256[:16]}.json"
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=output_dir,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return report


__all__ = ["write_validation_report"]

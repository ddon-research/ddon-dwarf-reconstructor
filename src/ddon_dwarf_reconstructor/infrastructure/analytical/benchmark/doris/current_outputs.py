"""Validate and summarize generated header-bundle outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def generation_output(target: Path) -> dict[str, Any]:
    """Return the published-header evidence for one generation target."""
    bundle_path = target / "ps4" / "header-bundle.manifest.json"
    if not bundle_path.is_file():
        return _missing_output(target)
    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        return _published_output(target, bundle_path, payload)
    except (OSError, TypeError, ValueError) as error:
        return _invalid_output(target, f"Header bundle manifest could not be validated: {error}")


def _missing_output(target: Path) -> dict[str, Any]:
    return {
        "status": "partial",
        "published": False,
        "reason": "No header bundle manifest was published.",
        "root": str(target),
        "files": [],
        "ordered_headers": [],
    }


def _invalid_output(target: Path, reason: str) -> dict[str, Any]:
    return {
        "status": "partial",
        "published": False,
        "root": str(target),
        "files": [],
        "ordered_headers": [],
        "reason": reason,
    }


def _published_output(target: Path, bundle_path: Path, payload: Any) -> dict[str, Any]:
    generation = payload.get("metadata", {}).get("generation", {})
    files = payload.get("files", {})
    ordered_headers = _ordered_headers(generation, files)
    evidence_files = [
        _file_evidence(target / "ps4" / name, files.get(name, {})) for name in ordered_headers
    ]
    files_observed = all(item["status"] == "observed" for item in evidence_files)
    published = generation.get("published") is True and generation.get("failed", 0) == 0
    status = "observed" if published and files_observed else "partial"
    return {
        "status": status,
        "published": published,
        "root": str(target),
        "bundle_manifest": str(bundle_path),
        "bundle_manifest_sha256": _sha256(bundle_path),
        "ordered_headers": ordered_headers,
        "file_count": len(evidence_files),
        "total_bytes": sum(int(item["bytes"] or 0) for item in evidence_files),
        "files": evidence_files,
    }


def _ordered_headers(generation: Any, files: Any) -> list[str]:
    if isinstance(generation, dict):
        outcomes = generation.get("outcomes", [])
        if isinstance(outcomes, list):
            for outcome in outcomes:
                if isinstance(outcome, dict) and isinstance(outcome.get("headers"), list):
                    return [str(item) for item in outcome["headers"]]
    return sorted(str(name) for name in files) if isinstance(files, dict) else []


def _file_evidence(path: Path, expected: Any) -> dict[str, Any]:
    expected_hash = expected.get("sha256") if isinstance(expected, dict) else None
    if not path.is_file():
        return {
            "status": "partial",
            "path": path.name,
            "bytes": None,
            "sha256": None,
            "expected_sha256": expected_hash,
        }
    actual_hash = _sha256(path)
    expected_bytes = expected.get("bytes") if isinstance(expected, dict) else None
    valid = (expected_hash is None or expected_hash == actual_hash) and (
        expected_bytes is None or int(expected_bytes) == path.stat().st_size
    )
    return {
        "status": "observed" if valid else "partial",
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": actual_hash,
        "expected_sha256": expected_hash,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["generation_output"]

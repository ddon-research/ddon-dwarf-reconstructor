"""Validate and summarize generated header-bundle outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def generation_output(target: Path) -> dict[str, Any]:
    """Return the published-header evidence for one generation target."""
    manifest_path, manifest_kind, error = _find_output_manifest(target)
    if manifest_path is None or manifest_kind is None:
        return _missing_output(target, error)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Output manifest is not an object")
        if manifest_kind == "symbols":
            return _published_symbol_output(target, manifest_path, payload)
        return _published_output(target, manifest_path, payload)
    except (OSError, TypeError, ValueError) as error:
        return _invalid_output(target, f"Header bundle manifest could not be validated: {error}")


def _find_output_manifest(target: Path) -> tuple[Path | None, str | None, str | None]:
    """Find the current versioned symbol manifest or the legacy header manifest."""
    candidates: list[tuple[Path, str]] = []
    legacy = target / "ps4" / "header-bundle.manifest.json"
    if legacy.is_file():
        candidates.append((legacy, "headers"))
    if target.is_dir():
        for platform_root in sorted(target.iterdir()):
            if not platform_root.is_dir() or not platform_root.name.startswith("ps4-"):
                continue
            manifest = platform_root / "symbols.manifest.json"
            if manifest.is_file():
                candidates.append((manifest, "symbols"))
    if not candidates:
        return None, None, None
    if len(candidates) > 1:
        paths = ", ".join(str(path) for path, _kind in candidates)
        return None, None, f"Multiple output manifests were published: {paths}"
    return (*candidates[0], None)


def _missing_output(target: Path, reason: str | None = None) -> dict[str, Any]:
    evidence = {
        "status": "partial",
        "published": False,
        "reason": reason or "No header bundle manifest was published.",
        "root": str(target),
        "files": [],
        "ordered_headers": [],
    }
    return evidence


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
        _file_evidence(bundle_path.parent / name, files.get(name, {})) for name in ordered_headers
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


def _published_symbol_output(target: Path, manifest_path: Path, payload: Any) -> dict[str, Any]:
    """Validate the versioned ``symbols.manifest.json`` header projection."""
    headers = _symbol_headers(payload)
    ordered_headers = sorted(headers)
    evidence_files = [
        _file_evidence(manifest_path.parent / name, headers.get(name, {}))
        for name in ordered_headers
    ]
    files_observed = _files_observed(evidence_files)
    roots_observed = _symbol_roots_observed(payload)
    published = roots_observed and files_observed
    return {
        "status": "observed" if published else "partial",
        "published": published,
        "root": str(target),
        "platform_root": str(manifest_path.parent),
        "bundle_manifest": str(manifest_path),
        "bundle_manifest_sha256": _sha256(manifest_path),
        "header_bundle_sha256": payload.get("header_bundle_sha256"),
        "ordered_headers": ordered_headers,
        "file_count": len(evidence_files),
        "total_bytes": sum(int(item["bytes"] or 0) for item in evidence_files),
        "files": evidence_files,
    }


def _symbol_headers(payload: dict[str, Any]) -> dict[str, Any]:
    headers = payload.get("headers", {})
    return headers if isinstance(headers, dict) else {}


def _files_observed(evidence_files: list[dict[str, Any]]) -> bool:
    return bool(evidence_files) and all(item["status"] == "observed" for item in evidence_files)


def _symbol_roots_observed(payload: dict[str, Any]) -> bool:
    requested = payload.get("requested_symbols", [])
    roots = payload.get("roots", {})
    if not isinstance(requested, list) or not isinstance(roots, dict) or not requested:
        return False
    return all(_root_is_success(roots, symbol) for symbol in requested)


def _root_is_success(roots: dict[str, Any], symbol: Any) -> bool:
    root = roots.get(symbol)
    return isinstance(root, dict) and root.get("status") == "success"


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

"""Reconcile compiler inputs with atomically published header manifests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True, slots=True)
class CompilerHeader:
    """One discovered header and its already measured content identity."""

    path: Path
    sha256: str
    byte_count: int


def _manifest_for(header: Path) -> Path | None:
    for directory in header.parents:
        candidate = directory / "symbols.manifest.json"
        if candidate.is_file():
            return candidate.resolve()
    return None


def _is_header_record(record: object) -> bool:
    return isinstance(record, dict) and record.get("kind") == "header"


def _expected_headers(manifest: dict[str, Any], root: Path) -> tuple[dict[Path, dict], list[str]]:
    expected: dict[Path, dict] = {}
    problems: list[str] = []
    file_hashes = manifest.get("file_hashes")
    if not isinstance(file_hashes, dict):
        return expected, [f"{root}: missing file_hashes map"]
    for name, record in sorted(file_hashes.items()):
        if not _is_header_record(record):
            continue
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            problems.append(f"{root}: unsafe header path {name!r}")
            continue
        path = (root / Path(*relative.parts)).resolve()
        if not path.is_relative_to(root):
            problems.append(f"{root}: header escapes publication root {name!r}")
            continue
        expected[path] = record
    if manifest.get("header_count") != len(expected):
        problems.append(f"{root}: header_count differs from file_hashes")
    return expected, problems


def _read_manifest(path: Path) -> tuple[dict[Path, dict], list[str], dict[str, str]]:
    data = path.read_bytes()
    identity = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        manifest = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as error:
        return {}, [f"{path}: invalid manifest: {error}"], identity
    if not isinstance(manifest, dict):
        return {}, [f"{path}: manifest root is not an object"], identity
    entries, errors = _expected_headers(manifest, path.parent.resolve())
    return entries, errors, identity


def _compare_headers(
    expected: dict[Path, dict], discovered: tuple[CompilerHeader, ...]
) -> list[str]:
    observed = {header.path.resolve(): header for header in discovered}
    diagnostics = [
        f"{path}: published header was not attempted"
        for path in sorted(expected.keys() - observed.keys())
    ]
    diagnostics.extend(
        f"{path}: attempted header has no publication record"
        for path in sorted(observed.keys() - expected.keys())
    )
    for path in sorted(expected.keys() & observed.keys()):
        record, header = expected[path], observed[path]
        if record.get("sha256") != header.sha256 or record.get("bytes") != header.byte_count:
            diagnostics.append(f"{path}: published header hash or size differs")
    return diagnostics


def inspect_manifest_binding(
    headers: Iterable[CompilerHeader], input_roots: Iterable[Path] = ()
) -> dict[str, Any]:
    """Fail closed when any compiler unit lacks matching publication evidence."""
    discovered = tuple(headers)
    manifests = {path for header in discovered if (path := _manifest_for(header.path)) is not None}
    for root in input_roots:
        manifests.update(root.resolve().rglob("symbols.manifest.json"))
    ordered_manifests = sorted(manifests)
    if not ordered_manifests:
        return {
            "status": "not_observed",
            "manifests": [],
            "expected_header_count": None,
            "diagnostics": ["No symbols.manifest.json binds the discovered headers"],
        }
    expected: dict[Path, dict] = {}
    diagnostics: list[str] = []
    manifest_records: list[dict[str, str]] = []
    for path in ordered_manifests:
        entries, errors, identity = _read_manifest(path)
        manifest_records.append(identity)
        diagnostics.extend(errors)
        for header_path, record in entries.items():
            if header_path in expected:
                diagnostics.append(f"{header_path}: listed by multiple manifests")
            expected[header_path] = record
    diagnostics.extend(_compare_headers(expected, discovered))
    return {
        "status": "mismatch" if diagnostics else "matched",
        "manifests": manifest_records,
        "expected_header_count": len(expected),
        "diagnostics": diagnostics,
    }

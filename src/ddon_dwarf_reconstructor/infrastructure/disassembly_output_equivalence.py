"""Output-equivalence manifests for the current flat symbol publisher.

The publisher emits byte artifacts beside two JSON documents.  Byte artifacts
are compared exactly.  The implementation report is compared through its
allowlisted runtime normalization, while the symbols manifest excludes only
the report hash/size fields that necessarily change when that report contains
run-specific diagnostics.  The manifest's own file declarations are checked
against the files on disk before a comparison is accepted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..core.content_hash import sha256_file

SCHEMA_VERSION = "output-equivalence/1"
_REPORT_NAME = "implementation-report.json"
_SYMBOL_MANIFEST_NAME = "symbols.manifest.json"
_JSON_NAMES = frozenset({_REPORT_NAME, _SYMBOL_MANIFEST_NAME})
_EXACT_KINDS = {
    ".h": "header",
    ".hpp": "header",
    ".asm": "raw_assembly",
    ".s": "canonical_assembly",
    ".o": "object",
}
_SHA256_LENGTH = 64
_VOLATILE_REPORT_PATHS = frozenset(
    {
        ("relocation_cache_path",),
        ("tool_invocations", "*", "duration_ms"),
        ("tool_invocations", "*", "stdout_path"),
        ("tool_invocations", "*", "stderr_path"),
    }
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _relative(path: Path, root: Path) -> str:
    if path.is_symlink():
        raise ValueError(f"symbolic-link output is not valid evidence: {path}")
    relative = path.relative_to(root).as_posix()
    if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError(f"unsafe output path: {relative!r}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"output path escapes root: {path}") from error
    return relative


def _kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _EXACT_KINDS:
        return _EXACT_KINDS[suffix]
    if path.name in _JSON_NAMES or suffix == ".json":
        return "json"
    return "other"


def _record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "kind": _kind(path),
    }


def _safe_declared_path(relative: str) -> Path:
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or not relative
        or any(part in {"", ".", ".."} for part in candidate.as_posix().split("/"))
    ):
        raise ValueError(f"manifest declares unsafe relative path: {relative!r}")
    return candidate


def _validate_hash_record(relative: str, value: Any) -> tuple[int, str]:
    if not isinstance(value, dict):
        raise ValueError(f"manifest hash record is not an object: {relative}")
    size = value.get("bytes")
    digest = value.get("sha256")
    if not isinstance(size, int) or size < 0:
        raise ValueError(f"manifest byte count is invalid: {relative}")
    if not isinstance(digest, str) or len(digest) != _SHA256_LENGTH:
        raise ValueError(f"manifest SHA-256 is invalid: {relative}")
    try:
        int(digest, 16)
    except ValueError as error:
        raise ValueError(f"manifest SHA-256 is invalid: {relative}") from error
    return size, digest


def _validate_declared_files(root: Path, payload: dict[str, Any]) -> None:
    declared = payload.get("file_hashes")
    if not isinstance(declared, dict):
        raise ValueError("symbols manifest must declare file_hashes")
    physical = {
        _relative(path, root): path
        for path in root.rglob("*")
        if path.is_file() and path.name != _SYMBOL_MANIFEST_NAME
    }
    if set(declared) != set(physical):
        missing = sorted(set(declared) - set(physical))
        extra = sorted(set(physical) - set(declared))
        raise ValueError(
            f"symbols manifest inventory mismatch (missing={missing[:5]}, extra={extra[:5]})"
        )
    for relative, value in declared.items():
        _safe_declared_path(relative)
        size, digest = _validate_hash_record(relative, value)
        path = physical[relative]
        actual = _record(path, root)
        if actual["bytes"] != size or actual["sha256"] != digest:
            raise ValueError(f"symbols manifest hash mismatch: {relative}")


def _validate_implementation_declarations(root: Path, payload: dict[str, Any]) -> None:
    implementation = payload.get("implementation")
    if implementation is None:
        return
    if not isinstance(implementation, dict):
        raise ValueError("symbols manifest implementation must be an object")
    _validate_report_declaration(root, implementation)
    _validate_implementation_files(root, implementation)


def _validate_report_declaration(root: Path, implementation: dict[str, Any]) -> None:
    report_path = implementation.get("report_path")
    if report_path is None:
        return
    if not isinstance(report_path, str):
        raise ValueError("implementation report_path must be a string")
    report = root / _safe_declared_path(report_path)
    if not report.is_file():
        raise ValueError(f"implementation report is missing: {report_path}")
    report_digest = sha256_file(report)
    if implementation.get("report_sha256") != report_digest:
        raise ValueError("implementation report hash does not match symbols manifest")


def _validate_implementation_files(root: Path, implementation: dict[str, Any]) -> None:
    files = implementation.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("implementation files must be an object")
    for relative, value in files.items():
        _safe_declared_path(relative)
        size, digest = _validate_hash_record(relative, value)
        path = root / relative
        if not path.is_file():
            raise ValueError(f"implementation artifact is missing: {relative}")
        actual = _record(path, root)
        if actual["bytes"] != size or actual["sha256"] != digest:
            raise ValueError(f"implementation artifact hash mismatch: {relative}")


def _normalize_symbols_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    implementation = normalized.get("implementation")
    if isinstance(implementation, dict):
        implementation.pop("report_sha256", None)
    file_hashes = normalized.get("file_hashes")
    if isinstance(file_hashes, dict):
        file_hashes.pop(_REPORT_NAME, None)
    return normalized


def _is_volatile_report_path(path: tuple[str, ...]) -> bool:
    return path in _VOLATILE_REPORT_PATHS


def _normalize_implementation_report(value: Any, path: tuple[str, ...] = ()) -> Any:
    if _is_volatile_report_path(path):
        return None if value is None else f"<VOLATILE:{path[-1]}>"
    if isinstance(value, dict):
        return {
            str(key): _normalize_implementation_report(item, (*path, str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_implementation_report(item, (*path, "*")) for item in value]
    return value


def _json_record(path: Path, root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON output: {_relative(path, root)}") from error
    relative = _relative(path, root)
    if path.name == _REPORT_NAME:
        if not isinstance(payload, dict):
            raise ValueError("implementation report must be a JSON object")
        normalized = _normalize_implementation_report(payload)
    elif path.name == _SYMBOL_MANIFEST_NAME:
        if not isinstance(payload, dict):
            raise ValueError("symbols manifest must be a JSON object")
        _validate_declared_files(root, payload)
        _validate_implementation_declarations(root, payload)
        normalized = _normalize_symbols_manifest(payload)
    else:
        normalized = payload
    return {
        "path": relative,
        "kind": "json",
        "raw_sha256": sha256_file(path),
        "normalized_sha256": _digest(normalized),
    }


def _validate_profile(root: Path, context_enabled: bool | None) -> None:
    if context_enabled is False:
        context_files = [
            _relative(path, root) for path in root.rglob("*.context.json") if path.is_file()
        ]
        if context_files:
            raise ValueError(
                f"context-disabled output contains context artifacts: {context_files[:5]}"
            )


def build_output_equivalence_manifest(
    output_root: Path,
    *,
    source: Path | None = None,
    configuration: dict[str, Any] | None = None,
    profile: str | None = None,
    context_enabled: bool | None = None,
) -> dict[str, Any]:
    """Build a validated manifest for one flat publisher output root."""

    root = output_root.resolve()
    if not root.is_dir():
        raise ValueError(f"missing output root: {output_root}")
    _validate_profile(root, context_enabled)
    files: dict[str, dict[str, Any]] = {}
    json_records: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            if path.is_symlink():
                _relative(path, root)
            continue
        relative = _relative(path, root)
        if relative.endswith((".tmp", ".partial")) or ".staging-" in relative:
            raise ValueError(f"incomplete output artifact: {relative}")
        files[relative] = _record(path, root)
        if path.suffix.lower() == ".json":
            json_records[relative] = _json_record(path, root)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "profile": profile,
        "context_enabled": context_enabled,
        "source": _source_record(source),
        "configuration": configuration,
        "file_count": len(files),
        "categories": _categories(files),
        "files": dict(sorted(files.items())),
        "json": dict(sorted(json_records.items())),
    }


def _source_record(source: Path | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "path": str(source.resolve()),
        "bytes": source.stat().st_size,
        "sha256": sha256_file(source),
    }


def _categories(files: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in files.values():
        kind = str(record["kind"])
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def _validate_manifest_payload(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("unexpected schema_version")
    if manifest.get("status") != "complete":
        errors.append("manifest is not complete")
    files = manifest.get("files")
    if not isinstance(files, dict):
        return [*errors, "manifest files are missing"]
    errors.extend(_validate_manifest_files(files))
    errors.extend(_validate_manifest_json(files, manifest.get("json")))
    if manifest.get("file_count") != len(files):
        errors.append("manifest file_count does not match inventory")
    return errors


def _validate_manifest_files(files: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for relative, value in files.items():
        try:
            _safe_declared_path(relative)
            _validate_hash_record(relative, value)
        except ValueError as error:
            errors.append(str(error))
    return errors


def _validate_manifest_json(files: dict[str, Any], json_records: Any) -> list[str]:
    if not isinstance(json_records, dict):
        return ["manifest json records are missing"]
    errors: list[str] = []
    for relative, value in json_records.items():
        if relative not in files:
            errors.append(f"JSON record is not in file inventory: {relative}")
        if not isinstance(value, dict) or not isinstance(value.get("normalized_sha256"), str):
            errors.append(f"invalid JSON comparison record: {relative}")
    return errors


def compare_output_equivalence_manifests(
    expected: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """Compare two validated flat-output manifests without broad normalization."""

    differences = [
        f"invalid expected manifest: {error}" for error in _validate_manifest_payload(expected)
    ]
    differences.extend(
        f"invalid actual manifest: {error}" for error in _validate_manifest_payload(actual)
    )
    if differences:
        return differences
    differences.extend(_compare_contract_fields(expected, actual))
    differences.extend(_compare_file_inventory(expected, actual))
    return differences


def _compare_contract_fields(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    fields = ("schema_version", "status", "profile", "context_enabled", "source", "configuration")
    return [
        f"changed output contract field: {field}"
        for field in fields
        if expected.get(field) != actual.get(field)
    ]


def _compare_file_inventory(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    differences: list[str] = []
    expected_files = expected["files"]
    actual_files = actual["files"]
    expected_json = expected["json"]
    actual_json = actual["json"]
    for relative in sorted(set(expected_files) | set(actual_files)):
        if relative not in expected_files:
            differences.append(f"unexpected output: {relative}")
            continue
        if relative not in actual_files:
            differences.append(f"missing output: {relative}")
            continue
        expected_record = expected_files[relative]
        actual_record = actual_files[relative]
        if expected_record["kind"] == "json" and actual_record["kind"] == "json":
            if expected_json.get(relative, {}).get("normalized_sha256") != actual_json.get(
                relative, {}
            ).get("normalized_sha256"):
                differences.append(f"changed structured JSON evidence: {relative}")
        elif expected_record != actual_record:
            differences.append(f"changed byte artifact: {relative}")
        elif expected_record["kind"] != actual_record["kind"]:
            differences.append(f"changed artifact kind: {relative}")
    return differences


__all__ = [
    "SCHEMA_VERSION",
    "build_output_equivalence_manifest",
    "compare_output_equivalence_manifests",
]

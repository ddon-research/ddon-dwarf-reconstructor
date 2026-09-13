"""Strict external-output manifests for disassembly regression runs.

The manifest deliberately treats generated reports differently from byte artifacts.
Headers, assembly, objects, contexts, and auxiliary JSON are byte-exact. Reports and
bundles retain raw hashes for diagnosis but compare normalized evidence facts; output
roots and bounded tool timing do not weaken the regression boundary.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

from ..core.content_hash import sha256_bytes, sha256_file, sha256_text

SCHEMA_VERSION = "disassembly-regression/1"
_VOLATILE_REPORT_KEYS = frozenset(
    {"duration_ms", "stdout_path", "stderr_path", "relocation_cache_path"}
)
_BUNDLE_DERIVED_KEYS = frozenset({"bundle_sha256", "report_sha256"})
_EXACT_CLASSES = frozenset(
    {"header", "raw_assembly", "canonical_assembly", "object", "context", "other_json"}
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return sha256_bytes(_canonical(value))


def _safe_relative(path: Path, root: Path) -> str:
    if path.is_symlink():
        raise ValueError(f"symbolic-link artifacts are not allowed: {path}")
    relative = path.relative_to(root).as_posix()
    if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError(f"unsafe output path: {relative!r}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"output path escapes root: {path}") from error
    return relative


def _replace_output_root(value: str, root: Path) -> str:
    replacements = (str(root.resolve()), root.resolve().as_posix())
    result = value
    for prefix in sorted(replacements, key=len, reverse=True):
        result = result.replace(prefix, "<OUTPUT_ROOT>")
    return result


def normalize_report(value: Any, root: Path, key: str | None = None) -> Any:
    """Normalize only the explicitly allowlisted report runtime fields."""

    if key in _VOLATILE_REPORT_KEYS:
        return None if value is None else f"<VOLATILE:{key}>"
    if isinstance(value, dict):
        return {str(k): normalize_report(item, root, str(k)) for k, item in value.items()}
    if isinstance(value, list):
        return [normalize_report(item, root) for item in value]
    if isinstance(value, str):
        return _replace_output_root(value, root)
    return value


def _file_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _bundle_digest(bundle: Path, manifest_path: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(item for item in bundle.rglob("*") if item.is_file()):
        if path.resolve() == manifest_path.resolve():
            continue
        entries.append((_safe_relative(path, bundle), sha256_file(path)))
    digest = hashlib.sha256()
    for relative, value in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _count_value(counters: dict[str, Counter[str]], field: str, value: Any) -> None:
    if value is not None:
        counters.setdefault(field, Counter())[str(value)] += 1


def _count_method_values(counters: dict[str, Counter[str]], methods: list[dict[str, Any]]) -> None:
    for field in ("implementation_status", "assembly_status"):
        for method in methods:
            _count_value(counters, f"methods.{field}", method.get(field))


def _count_source_artifact_values(
    counters: dict[str, Counter[str]], methods: list[dict[str, Any]]
) -> None:
    field = "methods.source_artifact.generation_status"
    for method in methods:
        artifact = method.get("source_artifact")
        if isinstance(artifact, dict):
            _count_value(counters, field, artifact.get("generation_status"))


def _status_summary(reports: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = {}
    for report in reports:
        _count_value(counters, "status", report.get("status"))
        _count_value(counters, "source_status", report.get("source_status"))
        methods = report.get("methods", [])
        _count_method_values(counters, methods)
        _count_source_artifact_values(counters, methods)
    return {field: dict(sorted(counter.items())) for field, counter in sorted(counters.items())}


def _method_facts(
    report_path: str, report: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    identities: list[dict[str, Any]] = []
    descriptors: list[dict[str, Any]] = []
    for ordinal, method in enumerate(report.get("methods", [])):
        source = method.get("source_artifact")
        method_id = source.get("method_id") if isinstance(source, dict) else None
        identities.append(
            {
                "report": report_path,
                "ordinal": ordinal,
                "method_id": method_id,
                "owner": method.get("owner"),
                "method_name": method.get("method_name"),
                "signature": method.get("signature"),
                "implementation_status": method.get("implementation_status"),
                "assembly_status": method.get("assembly_status"),
            }
        )
        if not isinstance(source, dict):
            continue
        for descriptor in source.get("artifacts", []):
            descriptors.append(
                {
                    "report": report_path,
                    "method_id": method_id,
                    "kind": descriptor.get("kind"),
                    "path": descriptor.get("path"),
                    "sha256": descriptor.get("sha256"),
                    "byte_length": descriptor.get("byte_length"),
                    "producer": descriptor.get("producer"),
                    "role": descriptor.get("role"),
                    "content_type": descriptor.get("content_type"),
                }
            )
    return identities, descriptors


def _classify(path: Path) -> str:
    if path.name.endswith(".context.json"):
        return "context"
    if path.name.endswith(".raw.asm"):
        return "raw_assembly"
    if path.name.endswith(".s"):
        return "canonical_assembly"
    if path.name.endswith(".linked.o") or path.name.endswith(".o"):
        return "object"
    if path.suffix.lower() in {".h", ".hpp"}:
        return "header"
    return "other_json" if path.suffix.lower() == ".json" else "other"


def _validate_complete_path(relative: str, path: Path) -> None:
    if any(part.startswith(".staging") or ".backup-" in part for part in relative.split("/")):
        raise ValueError(f"incomplete staged artifact: {relative}")
    if path.suffix.lower() in {".tmp", ".partial"}:
        raise ValueError(f"incomplete temporary artifact: {relative}")


def _inspect_bundle(path: Path, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report_path = (path.parent / payload["report_path"]).resolve()
    expected_report_dir = (root / "ps4" / "implementations").resolve()
    if report_path.parent != expected_report_dir or not report_path.is_file():
        raise ValueError(f"bundle report path is unsafe: {path}")
    report_sha256 = sha256_file(report_path)
    if payload.get("report_sha256") != report_sha256:
        raise ValueError(f"bundle report hash mismatch: {path}")
    if payload.get("bundle_sha256") != _bundle_digest(path.parent, path):
        raise ValueError(f"bundle digest mismatch: {path}")
    stable = {key: value for key, value in payload.items() if key not in _BUNDLE_DERIVED_KEYS}
    return {
        "path": _safe_relative(path, root),
        "raw_sha256": sha256_file(path),
        "stable_sha256": _digest(stable),
        "stable_fields": stable,
        "report_path": _safe_relative(report_path, root),
        "report_sha256": report_sha256,
        "bundle_sha256": payload.get("bundle_sha256"),
    }


def _inspect_report(
    path: Path, root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    relative = _safe_relative(path, root)
    identities, descriptors = _method_facts(relative, report)
    return (
        {
            "path": relative,
            "raw_sha256": sha256_file(path),
            "normalized_sha256": _digest(normalize_report(report, root)),
            "schema_version": report.get("schema_version"),
            "root_symbol": report.get("root_symbol"),
            "status": report.get("status"),
            "method_count": len(report.get("methods", [])),
            "method_identity_sha256": _digest(identities),
            "artifact_descriptor_sha256": _digest(descriptors),
        },
        identities,
        descriptors,
    )


@dataclass(slots=True)
class _BatchScan:
    files: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)
    exact_files: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)
    reports: list[dict[str, Any]] = dataclass_field(default_factory=list)
    report_facts: list[dict[str, Any]] = dataclass_field(default_factory=list)
    source_bundles: list[dict[str, Any]] = dataclass_field(default_factory=list)
    categories: Counter[str] = dataclass_field(default_factory=Counter)
    identities: list[dict[str, Any]] = dataclass_field(default_factory=list)
    descriptors: list[dict[str, Any]] = dataclass_field(default_factory=list)
    byte_count: int = 0


def _generated_symbols(batch_root: Path) -> list[str]:
    return [
        path.name.split("-", 1)[1]
        for path in sorted((batch_root / "symbols").iterdir())
        if path.is_dir()
    ]


def _is_implementation_report(path: Path, batch_root: Path, relative: str) -> bool:
    return (
        relative.startswith("ps4/implementations/")
        and path.parent == batch_root / "ps4" / "implementations"
        and path.suffix == ".json"
    )


def _scan_batch_path(scan: _BatchScan, path: Path, batch_root: Path) -> None:
    if not path.is_file():
        return
    relative = _safe_relative(path, batch_root)
    _validate_complete_path(relative, path)
    record = _file_record(path)
    scan.files[relative] = record
    scan.byte_count += record["bytes"]
    if path.name == "source-bundle.manifest.json":
        scan.categories["bundle_manifest"] += 1
        scan.source_bundles.append(_inspect_bundle(path, batch_root))
    elif _is_implementation_report(path, batch_root, relative):
        scan.categories["implementation_report"] += 1
        fact, method_ids, artifact_descriptors = _inspect_report(path, batch_root)
        scan.report_facts.append(fact)
        scan.reports.append(json.loads(path.read_text(encoding="utf-8")))
        scan.identities.extend(method_ids)
        scan.descriptors.extend(artifact_descriptors)
    else:
        category = _classify(path)
        scan.categories[category] += 1
        scan.exact_files[relative] = record


def _scan_batch_files(batch_root: Path) -> _BatchScan:
    scan = _BatchScan()
    for path in sorted(batch_root.rglob("*")):
        _scan_batch_path(scan, path, batch_root)
    return scan


def _sort_batch_scan(scan: _BatchScan) -> None:
    scan.report_facts.sort(key=lambda item: item["path"])
    scan.source_bundles.sort(key=lambda item: item["path"])
    scan.identities.sort(key=lambda item: (item["report"], item["ordinal"]))
    scan.descriptors.sort(
        key=lambda item: (item["report"], item.get("method_id") or "", item.get("path") or "")
    )


def _validate_batch_sets(scan: _BatchScan, batch_name: str, symbols: list[str]) -> None:
    expected_reports = {
        f"ps4/implementations/{ordinal:04d}-{symbol}.json"
        for ordinal, symbol in enumerate(symbols, 1)
    }
    expected_bundles = {
        f"ps4/implementations/{ordinal:04d}-{symbol}/source-bundle.manifest.json"
        for ordinal, symbol in enumerate(symbols, 1)
    }
    if {item["path"] for item in scan.report_facts} != expected_reports:
        raise ValueError(f"{batch_name}: report set is incomplete or duplicated")
    if {item["path"] for item in scan.source_bundles} != expected_bundles:
        raise ValueError(f"{batch_name}: source-bundle set is incomplete or duplicated")


def _batch_manifest(batch_name: str, symbols: list[str], scan: _BatchScan) -> dict[str, Any]:
    return {
        "name": batch_name,
        "root_count": len(symbols),
        "symbols": symbols,
        "symbols_sha256": sha256_text("\n".join(symbols) + "\n"),
        "file_count": len(scan.files),
        "bytes": scan.byte_count,
        "categories": dict(sorted(scan.categories.items())),
        "status_summary": _status_summary(scan.reports),
        "files": dict(sorted(scan.files.items())),
        "exact_files": dict(sorted(scan.exact_files.items())),
        "implementation_reports": scan.report_facts,
        "source_bundles": scan.source_bundles,
        "method_identities": scan.identities,
        "artifact_descriptors": scan.descriptors,
        "method_count": len(scan.identities),
        "unique_method_id_count": len(
            {item["method_id"] for item in scan.identities if item["method_id"]}
        ),
        "artifact_descriptor_count": len(scan.descriptors),
        "method_identity_sha256": _digest(scan.identities),
        "artifact_descriptor_sha256": _digest(scan.descriptors),
    }


def _build_batch(
    batch_root: Path, batch_name: str, symbols: list[str]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not batch_root.is_dir():
        raise ValueError(f"missing batch output: {batch_root}")
    if _generated_symbols(batch_root) != symbols:
        raise ValueError(f"{batch_name}: generated symbol directories do not match symbols")
    scan = _scan_batch_files(batch_root)
    _sort_batch_scan(scan)
    _validate_batch_sets(scan, batch_name, symbols)
    return (
        _batch_manifest(batch_name, symbols, scan),
        scan.files,
        scan.identities,
        scan.descriptors,
    )


def _load_manifest_inputs(
    configuration_path: Path, roots_path: Path
) -> tuple[dict[str, Any], list[str], list[int]]:
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    roots = [
        line.strip() for line in roots_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len(roots) != 289 or len(set(roots)) != len(roots):
        raise ValueError("the frozen Season 2 root list must contain 289 unique roots")
    partitions = configuration["roots"]["partitions"]
    if sum(partitions) != len(roots):
        raise ValueError("root partitions do not cover the root list")
    return configuration, roots, partitions


def _read_batch_symbols(output_root: Path, batch_name: str) -> list[str]:
    return [
        line.strip()
        for line in (output_root / f"{batch_name}-symbols.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _build_batches(
    output_root: Path, roots: list[str], partitions: list[int]
) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    batches: list[dict[str, Any]] = []
    all_files: dict[str, dict[str, Any]] = {}
    all_identities: list[dict[str, Any]] = []
    all_descriptors: list[dict[str, Any]] = []
    start = 0
    for index, count in enumerate(partitions, 1):
        batch_name = f"batch-{index:03d}"
        symbols = _read_batch_symbols(output_root, batch_name)
        if symbols != roots[start : start + count]:
            raise ValueError(f"{batch_name}: symbol list does not match the frozen ordering")
        batch, files, identities, descriptors = _build_batch(
            output_root / batch_name, batch_name, symbols
        )
        batches.append(batch)
        all_files.update({f"{batch_name}/{path}": record for path, record in files.items()})
        all_identities.extend(identities)
        all_descriptors.extend(descriptors)
        start += count
    all_identities.sort(key=lambda item: (item["report"], item["ordinal"]))
    all_descriptors.sort(
        key=lambda item: (item["report"], item.get("method_id") or "", item.get("path") or "")
    )
    return batches, all_files, all_identities, all_descriptors


def _aggregate_status(batches: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    status_summary: dict[str, Counter[str]] = {}
    for batch in batches:
        for field, values in batch["status_summary"].items():
            status_summary.setdefault(field, Counter()).update(values)
    return {field: dict(sorted(values.items())) for field, values in sorted(status_summary.items())}


def _normalization_metadata() -> dict[str, Any]:
    return {
        "report_volatile_keys": sorted(_VOLATILE_REPORT_KEYS),
        "report_path_token": "<OUTPUT_ROOT>",
        "report_hash_policy": "sha256(canonical-json(normalized-report))",
        "stable_bundle_excluded_keys": sorted(_BUNDLE_DERIVED_KEYS),
        "exact_artifact_classes": sorted(_EXACT_CLASSES),
    }


def _aggregate_manifest(
    roots: list[str],
    batches: list[dict[str, Any]],
    all_files: dict[str, dict[str, Any]],
    all_identities: list[dict[str, Any]],
    all_descriptors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "root_count": len(roots),
        "file_count": len(all_files),
        "bytes": sum(record["bytes"] for record in all_files.values()),
        "header_count": sum(batch["categories"].get("header", 0) for batch in batches),
        "method_count": len(all_identities),
        "unique_method_id_count": len(
            {item["method_id"] for item in all_identities if item["method_id"]}
        ),
        "artifact_descriptor_count": len(all_descriptors),
        "implementation_report_count": sum(
            batch["categories"].get("implementation_report", 0) for batch in batches
        ),
        "source_bundle_count": sum(
            batch["categories"].get("bundle_manifest", 0) for batch in batches
        ),
        "status_summary": _aggregate_status(batches),
        "method_identity_sha256": _digest(all_identities),
        "artifact_descriptor_sha256": _digest(all_descriptors),
    }


def build_disassembly_manifest(
    output_root: Path,
    configuration_path: Path,
    roots_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    """Build and validate one complete four-batch regression manifest."""

    configuration, roots, partitions = _load_manifest_inputs(configuration_path, roots_path)
    batches, all_files, all_identities, all_descriptors = _build_batches(
        output_root, roots, partitions
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "normalization": _normalization_metadata(),
        "source": {
            "path": str(source_path.resolve()),
            "bytes": source_path.stat().st_size,
            "sha256": sha256_file(source_path),
        },
        "roots": {
            "path": str(roots_path.resolve()),
            "bytes": roots_path.stat().st_size,
            "sha256": sha256_file(roots_path),
            "count": len(roots),
            "unique_count": len(set(roots)),
            "ordering": roots,
            "partitions": partitions,
        },
        "configuration": {
            "path": str(configuration_path.resolve()),
            "sha256": sha256_file(configuration_path),
            "value": configuration,
        },
        "batches": batches,
        "aggregate": _aggregate_manifest(
            roots, batches, all_files, all_identities, all_descriptors
        ),
        "file_map": dict(sorted(all_files.items())),
    }


def write_manifest(manifest: dict[str, Any], destination: Path) -> None:
    """Publish a manifest atomically enough for an external evidence bundle."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)
    digest = sha256_file(destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="ascii"
    )


def _without_keys(items: list[dict[str, Any]], keys: set[str]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key not in keys} for item in items]


def _compare_batch_reports(
    expected: dict[str, Any], actual: dict[str, Any], name: str
) -> list[str]:
    expected_reports = [
        {key: value for key, value in item.items() if key != "raw_sha256"}
        for item in expected.get("implementation_reports", [])
    ]
    actual_reports = [
        {key: value for key, value in item.items() if key != "raw_sha256"}
        for item in actual.get("implementation_reports", [])
    ]
    return [f"changed normalized reports: {name}"] if expected_reports != actual_reports else []


def _compare_batch_bundles(
    expected: dict[str, Any], actual: dict[str, Any], name: str
) -> list[str]:
    derived_keys = {"raw_sha256", "report_sha256", "bundle_sha256"}
    expected_bundles = _without_keys(expected.get("source_bundles", []), derived_keys)
    actual_bundles = _without_keys(actual.get("source_bundles", []), derived_keys)
    if expected_bundles != actual_bundles:
        return [f"changed source bundles: {name}"]
    return []


def _compare_batch(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    name_value = expected.get("name")
    if not isinstance(name_value, str) or name_value != actual.get("name"):
        return [f"changed batch identity: {name_value}"]
    name = name_value
    differences: list[str] = []
    if expected.get("symbols") != actual.get("symbols"):
        differences.append(f"changed root ordering: {name}")
    if expected.get("exact_files") != actual.get("exact_files"):
        differences.append(f"changed exact file map: {name}")
    differences.extend(_compare_batch_reports(expected, actual, name))
    if expected.get("method_identities") != actual.get("method_identities"):
        differences.append(f"changed method identities: {name}")
    if expected.get("artifact_descriptors") != actual.get("artifact_descriptors"):
        differences.append(f"changed artifact descriptors: {name}")
    differences.extend(_compare_batch_bundles(expected, actual, name))
    return differences


def compare_disassembly_manifests(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Return strict differences; only raw report/bundle hashes may vary."""

    differences: list[str] = []
    for field in ("schema_version", "status", "normalization", "source", "roots", "configuration"):
        if expected.get(field) != actual.get(field):
            differences.append(f"changed manifest field: {field}")
    expected_aggregate = expected.get("aggregate", {})
    actual_aggregate = actual.get("aggregate", {})
    aggregate_fields = (
        "root_count",
        "file_count",
        "header_count",
        "method_count",
        "unique_method_id_count",
        "artifact_descriptor_count",
        "implementation_report_count",
        "source_bundle_count",
        "status_summary",
        "method_identity_sha256",
        "artifact_descriptor_sha256",
    )
    for field in aggregate_fields:
        if expected_aggregate.get(field) != actual_aggregate.get(field):
            differences.append(f"changed aggregate field: {field}")
    expected_batches = expected.get("batches", [])
    actual_batches = actual.get("batches", [])
    if len(expected_batches) != len(actual_batches):
        differences.append("changed batch count")
    for expected_batch, actual_batch in zip(expected_batches, actual_batches, strict=False):
        differences.extend(_compare_batch(expected_batch, actual_batch))
    return differences

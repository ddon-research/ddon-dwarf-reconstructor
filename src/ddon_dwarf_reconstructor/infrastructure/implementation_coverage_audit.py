"""Independent IDA cross-validation for implementation-report completeness."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

_MARKER = re.compile(r"^\s*//-----\s*\((?P<address>[^)]+)\)")
_FUNCTION_NAME = re.compile(
    r"(?P<name>(?:(?:[A-Za-z_~][A-Za-z0-9_~]*|operator\s+(?:new|delete))::)*"
    r"(?:[A-Za-z_~][A-Za-z0-9_~]*|operator\s+(?:new|delete)))\s*\("
)
_CALLING_CONVENTION = re.compile(r"\b__(?:fastcall|cdecl|thiscall|stdcall)\b")


def audit_implementation_coverage(
    implementation_report: Path,
    ida_c_dump: Path,
    output_dir: Path,
    *,
    elf: Path | None = None,
) -> Path:
    """Compare an existing report with IDA names without feeding IDA upstream."""
    report_payload = json.loads(implementation_report.read_text(encoding="utf-8"))
    _validate_implementation_report(report_payload)
    report_sha256 = _sha256(implementation_report) or "unavailable"
    method_rows = tuple(row for row in report_payload.get("methods", ()) if isinstance(row, dict))
    ida_names, ida_addresses, dump_sha256, parse_diagnostics = _read_ida_dump(ida_c_dump)
    observations, not_generated, match_counts = _compare_methods(method_rows, ida_addresses)

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "status": "partial" if parse_diagnostics else "observed",
        "authority": "cross-validation-only",
        "production_pipeline_uses_ida": False,
        "implementation_report": {
            "path": str(implementation_report.resolve()),
            "sha256": report_sha256,
            "schema_version": report_payload.get("schema_version"),
        },
        "elf": {
            "path": str(elf.resolve()) if elf is not None else None,
            "sha256": _sha256(elf) if elf is not None and elf.is_file() else None,
        },
        "ida_c_dump": {"path": str(ida_c_dump.resolve()), "sha256": dump_sha256},
        "counts": {
            "report_methods": len(method_rows),
            "ida_named_bodies": len(ida_names),
            **match_counts,
            "ida_body_without_generated_assembly": len(not_generated),
        },
        "possible_pipeline_gaps": not_generated,
        "observations": observations,
        "diagnostics": parse_diagnostics,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"implementation-coverage-audit-{report_sha256[:16]}.json"
    _atomic_json_write(output_path, payload)
    return output_path


def _validate_implementation_report(payload: object) -> None:
    """Reject validation or arbitrary reports at the IDA audit boundary."""
    if not isinstance(payload, dict):
        raise ValueError("implementation report must be a JSON object")
    if payload.get("schema_version") != "4.2":
        raise ValueError("IDA coverage audit requires implementation-discovery report schema 4.2")
    methods = payload.get("methods")
    if not isinstance(methods, list):
        raise ValueError("implementation report must contain a methods list")


def _compare_methods(
    method_rows: tuple[dict[str, Any], ...], ida_addresses: dict[str, set[int]]
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    observations: list[dict[str, object]] = []
    not_generated: list[dict[str, object]] = []
    counts = {
        "exact_name_matches": 0,
        "normalized_name_matches": 0,
        "ambiguous_matches": 0,
        "no_named_body": 0,
    }
    for row in method_rows:
        observation, match_kind, addresses = _method_observation(row, ida_addresses)
        observations.append(observation)
        _increment_match_counts(counts, match_kind, len(addresses))
        if addresses and row.get("assembly_status") != "matched":
            not_generated.append(observation)
    return observations, not_generated, counts


def _method_observation(
    row: dict[str, Any], ida_addresses: dict[str, set[int]]
) -> tuple[dict[str, object], str, tuple[int, ...]]:
    key = _method_key(row)
    normalized = _normalize(key)
    exact_addresses = tuple(sorted(ida_addresses.get(key, ())))
    normalized_addresses = tuple(sorted(ida_addresses.get(normalized, ())))
    addresses = exact_addresses or normalized_addresses
    match_kind = "exact" if exact_addresses else "normalized" if normalized_addresses else "none"
    return (
        {
            "owner": str(row.get("owner", "")),
            "method_name": str(row.get("method_name", "")),
            "method_key": key,
            "match_kind": match_kind,
            "ida_addresses": list(addresses),
            "generated_assembly_status": str(row.get("assembly_status", "")),
        },
        match_kind,
        addresses,
    )


def _increment_match_counts(counts: dict[str, int], match_kind: str, address_count: int) -> None:
    if match_kind == "exact":
        counts["exact_name_matches"] += 1
    elif match_kind == "normalized":
        counts["normalized_name_matches"] += 1
    else:
        counts["no_named_body"] += 1
    if address_count > 1:
        counts["ambiguous_matches"] += 1


def _read_ida_dump(
    path: Path,
) -> tuple[set[str], dict[str, set[int]], str, tuple[str, ...]]:
    names: set[str] = set()
    addresses: dict[str, set[int]] = {}
    diagnostics: list[str] = []
    digest = hashlib.sha256()
    current_address: int | None = None
    current_name: str | None = None
    try:
        with path.open("rb") as stream:
            for raw_line in stream:
                digest.update(raw_line)
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                marker = _MARKER.match(line)
                if marker is not None:
                    _record_body(current_address, current_name, names, addresses)
                    current_address = _parse_address(marker.group("address"))
                    current_name = None
                    continue
                if current_address is not None and current_name is None:
                    current_name = _extract_name(line)
            _record_body(current_address, current_name, names, addresses)
    except OSError as error:
        diagnostics.append(f"IDA C dump could not be streamed: {type(error).__name__}")
    return names, addresses, digest.hexdigest(), tuple(diagnostics)


def _record_body(
    address: int | None,
    name: str | None,
    names: set[str],
    addresses: dict[str, set[int]],
) -> None:
    if address is None or not name:
        return
    names.add(name)
    addresses.setdefault(name, set()).add(address)
    normalized = _normalize(name)
    addresses.setdefault(normalized, set()).add(address)


def _extract_name(line: str) -> str | None:
    line = _CALLING_CONVENTION.sub("", line)
    matches = tuple(_FUNCTION_NAME.finditer(line))
    return matches[-1].group("name") if matches else None


def _method_key(row: dict[str, Any]) -> str:
    owner = str(row.get("owner", "")).strip()
    method = str(row.get("method_name", "")).strip()
    return f"{owner}::{method}" if owner else method


def _normalize(value: str) -> str:
    text = _CALLING_CONVENTION.sub("", value).strip().replace("operator_new", "operator new")
    text = text.replace("operator_delete", "operator delete")
    text = re.sub(r"\s+", " ", text)
    parts = []
    for part in text.split("::"):
        part = re.sub(r"_(\d+)$", "", part)
        if part.startswith("_") and not part.startswith("__"):
            part = part[1:]
        parts.append(part)
    return "::".join(parts)


def _parse_address(value: str) -> int | None:
    try:
        return int(value.strip(), 0)
    except ValueError:
        try:
            return int(value.strip(), 16)
        except ValueError:
            return None


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary_path.replace(path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)


__all__ = ["audit_implementation_coverage"]

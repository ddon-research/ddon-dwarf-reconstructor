"""Bounded parsers for source-bound matching Orbis ``orbis-bin`` exports."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from ..domain.models.implementation_validation import (
    OrbisBinEvidence,
    OrbisBinStackSizeEvidence,
    ValidationStatus,
)
from ..domain.models.tool_evidence import ToolExport

STACK_SIZE_PROFILE = "orbis-bin-stack-sizes"
DYNAMIC_SYMBOL_PROFILE = "orbis-bin-dynamic-symbols"
_STACK_SIZE = re.compile(r"^\s*(?P<size>[0-9]+)\s+(?P<symbol>\S.*\S)\s*$")
_DYNAMIC_SYMBOL = re.compile(r"^\s*0x[0-9a-fA-F]+\s+-\s+.+")


def parse_stack_size_output(
    text: str,
    *,
    manifest_path: Path | None = None,
    output_sha256: str | None = None,
) -> tuple[OrbisBinStackSizeEvidence, ...]:
    """Parse the stable numeric/name rows emitted by ``orbis-bin -dss``."""
    records: list[OrbisBinStackSizeEvidence] = []
    for line in text.splitlines():
        match = _STACK_SIZE.match(line)
        if match is None:
            continue
        records.append(
            OrbisBinStackSizeEvidence(
                status=ValidationStatus.OBSERVED,
                symbol=match.group("symbol").strip(),
                stack_size_bytes=int(match.group("size")),
                manifest_path=str(manifest_path) if manifest_path is not None else None,
                output_sha256=output_sha256,
            )
        )
    if not records and text.strip():
        return (
            OrbisBinStackSizeEvidence(
                status=ValidationStatus.PARTIAL,
                symbol="",
                manifest_path=str(manifest_path) if manifest_path is not None else None,
                output_sha256=output_sha256,
                diagnostics=("orbis-bin stack-size output contained no numeric rows",),
            ),
        )
    return tuple(records)


def match_stack_size(
    records: Iterable[OrbisBinStackSizeEvidence], symbol: str
) -> OrbisBinStackSizeEvidence:
    """Match one demangled method name without guessing through duplicates."""
    matches = tuple(item for item in records if item.symbol == symbol)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return OrbisBinStackSizeEvidence(
            status=ValidationStatus.PARTIAL,
            symbol=symbol,
            diagnostics=("multiple orbis-bin stack-size rows matched the method name",),
        )
    return OrbisBinStackSizeEvidence(
        status=ValidationStatus.NOT_OBSERVED,
        symbol=symbol,
        diagnostics=("orbis-bin stack-size export did not contain the method name",),
    )


def parse_orbis_bin_exports(
    exports: Iterable[ToolExport],
    manifest_paths: Iterable[Path] = (),
) -> OrbisBinEvidence:
    """Parse recognized exports while retaining all other profiles as raw evidence."""
    grouped = _group_exports(exports)
    exports_by_profile = _unique_exports(grouped)
    manifest_by_key = _manifest_paths_by_key(manifest_paths)
    profiles = tuple(sorted(grouped))
    diagnostics = _duplicate_diagnostics(grouped)
    stack_records, parse_diagnostics = _parse_exports(exports_by_profile, manifest_by_key)
    diagnostics.extend(parse_diagnostics)
    status = _export_status(exports_by_profile, stack_records, diagnostics, grouped)
    dynamic_count = _dynamic_symbol_count(exports_by_profile, manifest_by_key)
    return OrbisBinEvidence(
        status=status,
        profiles=profiles,
        stack_sizes=tuple(stack_records),
        dynamic_symbol_count=dynamic_count,
        diagnostics=tuple(diagnostics),
    )


def _group_exports(exports: Iterable[ToolExport]) -> dict[str, list[ToolExport]]:
    grouped: dict[str, list[ToolExport]] = {}
    for export in exports:
        grouped.setdefault(export.profile, []).append(export)
    return grouped


def _unique_exports(grouped: dict[str, list[ToolExport]]) -> dict[str, ToolExport]:
    return {profile: values[0] for profile, values in grouped.items() if len(values) == 1}


def _duplicate_diagnostics(grouped: dict[str, list[ToolExport]]) -> list[str]:
    return [
        f"duplicate external-tool profile: {profile}"
        for profile, values in sorted(grouped.items())
        if len(values) > 1
    ]


def _parse_exports(
    exports: dict[str, ToolExport], manifest_by_key: dict[str, Path]
) -> tuple[list[OrbisBinStackSizeEvidence], list[str]]:
    records: list[OrbisBinStackSizeEvidence] = []
    diagnostics: list[str] = []
    for profile, export in sorted(exports.items()):
        parsed, parsed_diagnostics = _parse_export(
            profile, export, manifest_by_key.get(export.artifact_key)
        )
        records.extend(parsed)
        diagnostics.extend(item for record in parsed for item in record.diagnostics)
        diagnostics.extend(parsed_diagnostics)
    return records, diagnostics


def _export_status(
    exports: dict[str, ToolExport],
    records: list[OrbisBinStackSizeEvidence],
    diagnostics: list[str],
    grouped: dict[str, list[ToolExport]],
) -> ValidationStatus:
    if any(len(values) > 1 for values in grouped.values()) or any(
        _is_fatal_diagnostic(item) for item in diagnostics
    ):
        return ValidationStatus.FAILED
    if not records and DYNAMIC_SYMBOL_PROFILE not in exports:
        return ValidationStatus.NOT_OBSERVED
    return ValidationStatus.PARTIAL if diagnostics else ValidationStatus.OBSERVED


def _parse_export(
    profile: str, export: ToolExport, manifest_path: Path | None
) -> tuple[tuple[OrbisBinStackSizeEvidence, ...], tuple[str, ...]]:
    if export.output is None:
        return (), (f"{profile}: export has no output descriptor",)
    output_path = _output_path(export, manifest_path)
    if output_path is None:
        return (), (f"{profile}: output path could not be resolved",)
    try:
        text = output_path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return (), (f"{profile}: output could not be read: {type(error).__name__}",)
    if profile == STACK_SIZE_PROFILE:
        return (
            parse_stack_size_output(
                text,
                manifest_path=manifest_path,
                output_sha256=export.output.sha256,
            ),
            (),
        )
    if profile == DYNAMIC_SYMBOL_PROFILE:
        return (), _dynamic_symbol_diagnostics(text)
    return (), ()


def _dynamic_symbol_diagnostics(text: str) -> tuple[str, ...]:
    if not text.strip():
        return ("orbis-bin dynamic-symbol output was empty",)
    dynamic_count = sum(1 for line in text.splitlines() if _DYNAMIC_SYMBOL.match(line))
    return (
        ("orbis-bin dynamic-symbol output contained no symbol rows",) if dynamic_count == 0 else ()
    )


def _is_fatal_diagnostic(value: str) -> bool:
    return any(
        marker in value
        for marker in (
            "export has no output descriptor",
            "output path could not be resolved",
            "output could not be read",
        )
    )


def _dynamic_symbol_count(
    exports: dict[str, ToolExport], manifest_by_key: dict[str, Path]
) -> int | None:
    export = exports.get(DYNAMIC_SYMBOL_PROFILE)
    if export is None or export.output is None:
        return None
    path = _output_path(export, manifest_by_key.get(export.artifact_key))
    if path is None:
        return None
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if _DYNAMIC_SYMBOL.match(line)
        )
    except OSError:
        return None


def _manifest_paths_by_key(paths: Iterable[Path]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("artifact_key"), str):
                result[value["artifact_key"]] = path.resolve()
        except OSError, TypeError, ValueError, json.JSONDecodeError:
            continue
    return result


def _output_path(export: ToolExport, manifest_path: Path | None) -> Path | None:
    if export.output is None or manifest_path is None:
        return None
    candidate = (manifest_path.parent / export.output.path).resolve()
    try:
        candidate.relative_to(manifest_path.parent.resolve())
    except ValueError:
        return None
    return candidate


__all__ = [
    "DYNAMIC_SYMBOL_PROFILE",
    "STACK_SIZE_PROFILE",
    "match_stack_size",
    "parse_orbis_bin_exports",
    "parse_stack_size_output",
]

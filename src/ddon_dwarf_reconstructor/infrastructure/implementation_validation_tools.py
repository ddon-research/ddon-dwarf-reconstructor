"""External tool, SDK-resolution, and stack-size joins for implementation validation."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..domain.models.implementation_validation import (
    CompilerEvidence,
    ExternalToolObservation,
    MethodValidationEvidence,
    OrbisBinStackSizeEvidence,
    ValidationStatus,
)
from .implementation_abi_probe_manifest import load_probe_manifest
from .orbis_bin_evidence import match_stack_size
from .orbis_toolchain_contracts import SDK12_ROOT, profile_id_for_path
from .toolchain_exports import load_tool_exports


def load_external_exports(
    manifest_paths: tuple[Path, ...],
    source: Path,
    toolchain_profile: str,
    diagnostics: list[str],
) -> tuple[tuple[Any, Path | None], ...]:
    """Load complete exports and reject source, path, or SDK-family drift."""
    if not manifest_paths:
        return ()
    try:
        exports = load_tool_exports(manifest_paths, source)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        diagnostics.append(f"external tool evidence was rejected: {type(error).__name__}")
        return ()
    if _has_mixed_toolchain(exports, toolchain_profile):
        diagnostics.append("external tool evidence was rejected: toolchain profile does not match")
        return ()
    lookup = _manifest_lookup(manifest_paths)
    return tuple((export, lookup.get(export.artifact_key)) for export in exports)


def load_or_run_abi_probes(
    manifest_path: Path | None,
    compiler: Path | None,
    output_dir: Path,
    readelf: Path | None,
    toolchain_profile: str,
    timeout_seconds: float | None,
    diagnostics: list[str],
    *,
    probe_runner: Callable[..., tuple[CompilerEvidence, ...]],
) -> tuple[CompilerEvidence, ...]:
    """Reuse a validated compiler matrix or run the bounded probe set."""
    if manifest_path is not None:
        try:
            manifest = load_probe_manifest(manifest_path.resolve())
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            diagnostics.append(f"ABI probe manifest could not be loaded: {type(error).__name__}")
            return ()
        if manifest.toolchain_profile != toolchain_profile:
            diagnostics.append(
                "ABI probe manifest toolchain profile does not match the validation profile"
            )
            return ()
        return manifest.probes
    return probe_runner(
        compiler,
        output_dir / "abi-probes",
        readelf=readelf,
        timeout_seconds=timeout_seconds,
        toolchain_profile=toolchain_profile,
    )


def external_observation(export: Any, manifest_path: Path | None) -> ExternalToolObservation:
    """Convert one complete tool export to the validation report projection."""
    output_path = None
    output_sha256 = None
    if export.output is not None and manifest_path is not None:
        output_path = str((manifest_path.parent / export.output.path).resolve())
        output_sha256 = export.output.sha256
    return ExternalToolObservation(
        profile=export.profile,
        authority=export.authority,
        status=ValidationStatus.OBSERVED,
        source_sha256=export.source_sha256,
        tool=export.tool_path,
        tool_sha256=export.tool_sha256,
        tool_version=export.tool_version,
        manifest_path=str(manifest_path) if manifest_path is not None else None,
        output_path=output_path,
        output_sha256=output_sha256,
        diagnostics=export.diagnostics,
    )


def attach_stack_size_evidence(
    methods: tuple[MethodValidationEvidence, ...],
    stack_sizes: tuple[OrbisBinStackSizeEvidence, ...],
) -> tuple[MethodValidationEvidence, ...]:
    """Join exact Orbis utility stack-size rows without guessing through duplicates."""
    if not stack_sizes:
        return methods
    return tuple(
        replace(method, stack_size=match_stack_size(stack_sizes, method.method_name))
        for method in methods
    )


def resolve_sdk_tool(sdk_root: Path | None, name: str) -> Path | None:
    """Resolve an explicitly selected SDK tool without copying SDK content."""
    roots = _sdk_roots(sdk_root)
    return next(
        (
            candidate.resolve()
            for root in roots
            for candidate in _tool_candidates(root, name)
            if candidate.exists()
        ),
        None,
    )


def _sdk_roots(sdk_root: Path | None) -> tuple[Path, ...]:
    roots = [sdk_root] if sdk_root is not None else []
    environment_root = os.environ.get("ORBIS_SDK_ROOT")
    if environment_root:
        roots.append(Path(environment_root))
    roots.append(SDK12_ROOT)
    return tuple(root for root in roots if root is not None)


def _tool_candidates(root: Path, name: str) -> tuple[Path, Path]:
    directory = root / "host_tools" / "bin"
    return directory / name, directory / f"{name}.exe"


def _has_mixed_toolchain(exports: tuple[Any, ...], profile: str) -> bool:
    return any(
        (inferred := profile_id_for_path(Path(export.tool_path))) is not None
        and inferred != profile
        for export in exports
    )


def _manifest_lookup(paths: tuple[Path, ...]) -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError, TypeError, ValueError, json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("artifact_key"), str):
            lookup[value["artifact_key"]] = path.resolve()
    return lookup


__all__ = [
    "attach_stack_size_evidence",
    "external_observation",
    "load_external_exports",
    "load_or_run_abi_probes",
    "resolve_sdk_tool",
]

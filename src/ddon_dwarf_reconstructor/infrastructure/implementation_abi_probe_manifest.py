"""Atomic publication and validation of compiler ABI probe manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.content_hash import sha256_file
from ..domain.models.implementation_validation import (
    CompilerEvidence,
    CompilerProbeManifest,
    ValidationStatus,
)
from .artifact_io import atomic_write_text
from .orbis_toolchain_contracts import SDK12_PROFILE_ID
from .toolchain_process import ToolIdentityCache

_TARGET_TRIPLE = "x86_64-scei-ps4"
_PROFILE = "orbis-compiler-abi"


def aggregate_probe_status(results: tuple[CompilerEvidence, ...]) -> ValidationStatus:
    """Collapse probe outcomes without hiding an individual failure."""
    if not results:
        return ValidationStatus.NOT_OBSERVED
    statuses = {item.status for item in results}
    if statuses == {ValidationStatus.OBSERVED}:
        return ValidationStatus.OBSERVED
    if ValidationStatus.FAILED in statuses:
        return ValidationStatus.FAILED
    if ValidationStatus.BLOCKED in statuses:
        return ValidationStatus.BLOCKED
    if ValidationStatus.UNAVAILABLE in statuses:
        return ValidationStatus.UNAVAILABLE
    return ValidationStatus.PARTIAL


def build_probe_manifest(
    results: tuple[CompilerEvidence, ...],
    compiler: Path,
    *,
    toolchain_profile: str = SDK12_PROFILE_ID,
    identity_cache: ToolIdentityCache | None = None,
) -> CompilerProbeManifest:
    """Build a reusable manifest from one completed probe matrix."""
    identity = (identity_cache or ToolIdentityCache()).observe(
        compiler,
        profile="compiler-abi-manifest",
    )
    return CompilerProbeManifest(
        profile=_PROFILE,
        toolchain_profile=toolchain_profile,
        target_triple=_TARGET_TRIPLE,
        compiler=str(compiler.resolve()),
        compiler_sha256=identity.sha256 or sha256_file(compiler),
        compiler_version=identity.version or "unavailable",
        probes=results,
        status=aggregate_probe_status(results),
        diagnostics=() if results else ("no ABI probe results were produced",),
    )


def write_probe_manifest(manifest: CompilerProbeManifest, path: Path) -> Path:
    """Publish one probe manifest atomically."""
    path = path.resolve()
    atomic_write_text(path, json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n")
    return path


def load_probe_manifest(path: Path) -> CompilerProbeManifest:
    """Load a reusable probe manifest and reject malformed schema/status data."""
    path = path.resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ValueError(f"Unsupported compiler probe manifest: {path}")
    probes_value = value.get("probes")
    if not isinstance(probes_value, list):
        raise ValueError("Compiler probe manifest probes must be a list")
    manifest = CompilerProbeManifest(
        profile=_required_string(value, "profile"),
        toolchain_profile=_required_string(value, "toolchain_profile"),
        target_triple=_required_string(value, "target_triple"),
        compiler=_required_string(value, "compiler"),
        compiler_sha256=_required_string(value, "compiler_sha256"),
        compiler_version=_required_string(value, "compiler_version"),
        probes=tuple(_compiler_evidence_from_dict(item) for item in probes_value),
        status=ValidationStatus(_required_string(value, "status")),
        diagnostics=tuple(str(item) for item in value.get("diagnostics", [])),
    )
    _validate_probe_manifest(manifest)
    return manifest


def _validate_probe_manifest(manifest: CompilerProbeManifest) -> None:
    _validate_manifest_identity(manifest)
    compiler = _validated_hashed_path(
        manifest.compiler, manifest.compiler_sha256, "compiler executable"
    )
    profiles: set[str] = set()
    for probe in manifest.probes:
        _validate_probe_identity(probe, manifest, compiler, profiles)
        _validate_probe_artifacts(probe)
    if aggregate_probe_status(manifest.probes) is not manifest.status:
        raise ValueError("Compiler probe manifest status does not match its probe entries")


def _validate_manifest_identity(manifest: CompilerProbeManifest) -> None:
    if manifest.profile != _PROFILE:
        raise ValueError("Unsupported compiler probe profile")
    if manifest.target_triple != _TARGET_TRIPLE:
        raise ValueError("Compiler probe target triple does not match the PS4 contract")


def _validate_probe_identity(
    probe: CompilerEvidence,
    manifest: CompilerProbeManifest,
    compiler: Path,
    profiles: set[str],
) -> None:
    if probe.profile is None:
        raise ValueError("Compiler ABI probe profile is missing")
    if probe.profile in profiles:
        raise ValueError(f"Duplicate compiler ABI probe: {probe.profile}")
    profiles.add(probe.profile)
    if probe.toolchain_profile != manifest.toolchain_profile:
        raise ValueError(f"Compiler ABI probe profile mismatch: {probe.profile}")
    if probe.tool is not None and Path(probe.tool).resolve() != compiler:
        raise ValueError(f"Compiler ABI probe tool mismatch: {probe.profile}")
    if probe.tool_sha256 is not None and probe.tool_sha256 != manifest.compiler_sha256:
        raise ValueError(f"Compiler ABI probe tool hash mismatch: {probe.profile}")


def _validate_probe_artifacts(probe: CompilerEvidence) -> None:
    for label, path, digest in (
        ("source", probe.source_path, probe.source_sha256),
        ("assembly", probe.assembly_path, probe.assembly_sha256),
        ("object", probe.output_path, probe.output_sha256),
    ):
        if path is None:
            continue
        if digest is None:
            raise ValueError(f"Compiler ABI probe {label} hash is missing: {probe.profile}")
        _validated_hashed_path(path, digest, f"compiler ABI probe {label}")


def _validated_hashed_path(path: str, expected: str, label: str) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_file():
        raise ValueError(f"{label} does not exist: {candidate}")
    if sha256_file(candidate) != expected:
        raise ValueError(f"{label} hash does not match: {candidate}")
    return candidate


def _compiler_evidence_from_dict(value: object) -> CompilerEvidence:
    if not isinstance(value, dict):
        raise ValueError("Compiler probe entry must be an object")
    return CompilerEvidence(
        status=ValidationStatus(_required_string(value, "status")),
        profile=_optional_string(value.get("profile")),
        tool=_optional_string(value.get("tool")),
        tool_sha256=_optional_string(value.get("tool_sha256")),
        version=_optional_string(value.get("version")),
        command=tuple(str(item) for item in value.get("command", [])),
        stdout_path=_optional_string(value.get("stdout_path")),
        stderr_path=_optional_string(value.get("stderr_path")),
        output_path=_optional_string(value.get("output_path")),
        output_sha256=_optional_string(value.get("output_sha256")),
        assembly_path=_optional_string(value.get("assembly_path")),
        assembly_sha256=_optional_string(value.get("assembly_sha256")),
        source_path=_optional_string(value.get("source_path")),
        source_sha256=_optional_string(value.get("source_sha256")),
        toolchain_profile=_optional_string(value.get("toolchain_profile")),
        assembly_profile=str(value.get("assembly_profile", "byte-replay")),
        object_metadata=dict(value.get("object_metadata", {})),
        diagnostics=tuple(str(item) for item in value.get("diagnostics", [])),
    )


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"Compiler probe manifest field {key} must be a non-empty string")
    return item


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "aggregate_probe_status",
    "build_probe_manifest",
    "load_probe_manifest",
    "write_probe_manifest",
]

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ..core.content_hash import header_bundle_sha256, sha256_file, sha256_text
from ..core.path_policy import create_header_filename
from ..core.platform import ELFPlatform
from ..domain.models.implementation_evidence import (
    ArtifactDescriptor,
    ImplementationArtifactProfile,
    ImplementationDiscoveryReport,
    MethodAssemblyEvidence,
    SourceArtifactMetadata,
)
from ..domain.ports.implementation_artifacts import ImplementationContextEnrichmentProvider
from .artifact_io import content_sha256, safe_relative_path, temporary_text
from .implementation_artifacts import (
    add_context_artifact,
    render_canonical_method_artifact,
)
from .implementation_context import normalize_raw_assembly

RenderedContent = str | bytes


class ImplementationArtifactRenderer(Protocol):
    """Render one explicitly selected derived implementation profile."""

    profile: ImplementationArtifactProfile

    def render(
        self,
        method: MethodAssemblyEvidence,
        includes: tuple[str, ...],
        method_id: str,
        report_filename: str,
    ) -> tuple[SourceArtifactMetadata, dict[Path, RenderedContent] | None]: ...


class CanonicalAssemblyArtifactRenderer:
    """Render exact-byte assembly and an optional accepted Orbis object."""

    profile = ImplementationArtifactProfile.CANONICAL_ASSEMBLY

    def __init__(self, assembler: Path | None = None) -> None:
        self.assembler = assembler

    def render(
        self,
        method: MethodAssemblyEvidence,
        includes: tuple[str, ...],
        method_id: str,
        report_filename: str,
    ) -> tuple[SourceArtifactMetadata, dict[Path, RenderedContent] | None]:
        del report_filename
        return render_canonical_method_artifact(method, includes, method_id, self.assembler)


class AtomicImplementationReportPublisher:
    """Publish one canonical report and an optional assembly/object bundle."""

    BUNDLE_MANIFEST_NAME = "source-bundle.manifest.json"
    BUNDLE_SCHEMA_VERSION = "3.1"
    HEADER_MANIFEST_NAME = "header-bundle.manifest.json"

    def __init__(
        self,
        renderer: ImplementationArtifactRenderer | None = None,
        *,
        assembler: Path | None = None,
        context_evidence: ImplementationContextEnrichmentProvider | None = None,
    ) -> None:
        self._renderer = renderer or CanonicalAssemblyArtifactRenderer(assembler)
        self._context_evidence = context_evidence or {}

    def publish(
        self,
        output_root: Path,
        platform: ELFPlatform,
        index: int,
        symbol: str,
        report: ImplementationDiscoveryReport,
        *,
        emit_sources: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        """Atomically publish the current report and its selected derived view."""
        if report.artifact_profile is not self._renderer.profile:
            raise ValueError(
                f"unsupported implementation artifact profile: {report.artifact_profile.value}"
            )
        target_dir = output_root / platform.value / "implementations"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_symbol = _safe_symbol(symbol)
        target = target_dir / f"{index:04d}-{safe_symbol}.json"
        bundle_target = target_dir / f"{index:04d}-{safe_symbol}"
        bound_report = _bind_header_manifest(report, output_root, platform)
        if not emit_sources:
            report_without_sources = _without_sources(bound_report)
            _commit_bundle_and_report(
                None,
                bundle_target,
                target,
                report_without_sources,
            )
            return target

        stage, published_report = self._stage_sources(
            target_dir,
            index,
            symbol,
            bound_report,
            headers or {},
        )
        try:
            _commit_bundle_and_report(stage, bundle_target, target, published_report)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        return target

    def _stage_sources(
        self,
        target_dir: Path,
        index: int,
        symbol: str,
        report: ImplementationDiscoveryReport,
        headers: Mapping[str, str],
    ) -> tuple[Path, ImplementationDiscoveryReport]:
        bundle_name = f"{index:04d}-{_safe_symbol(symbol)}"
        stage = target_dir / f".{bundle_name}.staging-{uuid4().hex}"
        includes = _header_includes(report, symbol, headers)
        _validate_header_mapping(report, headers)
        stage.mkdir(parents=True, exist_ok=False)
        metadata: list[SourceArtifactMetadata] = []
        rendered_methods: list[MethodAssemblyEvidence] = []
        report_filename = f"{bundle_name}.json"
        try:
            method_ids: set[str] = set()
            for original_method in report.methods:
                method = replace(
                    original_method,
                    raw_disassembly=normalize_raw_assembly(original_method.raw_disassembly),
                )
                method_id = stable_method_id(method)
                if method_id in method_ids:
                    raise ValueError(f"duplicate implementation method id: {method_id}")
                method_ids.add(method_id)
                artifact, rendered = self._renderer.render(
                    method,
                    includes,
                    method_id,
                    report_filename,
                )
                artifact, rendered = add_context_artifact(
                    method,
                    method_id,
                    report,
                    artifact,
                    rendered,
                    self._context_evidence.get(method_id),
                    getattr(self._renderer, "assembler", None),
                )
                _validate_rendered_artifact(artifact, method_id, includes, rendered)
                metadata.append(artifact)
                rendered_methods.append(replace(method, source_artifact=artifact))
                if rendered is not None:
                    for relative_path, content in rendered.items():
                        _write_content(stage / relative_path, content)
            published = replace(
                report,
                methods=tuple(rendered_methods),
                source_status=(
                    "generated" if any(item.artifacts for item in metadata) else "not_eligible"
                ),
            )
            return stage, published
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise


def stable_method_id(method: MethodAssemblyEvidence) -> str:
    """Return a deterministic, collision-resistant method directory identifier."""
    identity = "|".join(
        (
            method.owner,
            method.signature,
            str(method.declaration_die_offset),
            str(method.selected_implementation_die_offset),
            str(method.selected_function_address),
        )
    )
    slug = _safe_symbol(f"{method.owner}-{method.method_name}")[:48]
    return f"{slug}-{sha256_text(identity)[:16]}"


def _validate_header_mapping(
    report: ImplementationDiscoveryReport,
    headers: Mapping[str, str],
) -> None:
    if not headers and report.header_files:
        raise ValueError("source emission requires the generated header mapping")
    if not headers:
        return
    missing = tuple(name for name in report.header_files if name not in headers)
    if missing:
        raise ValueError(f"header mapping is missing generated files: {', '.join(missing)}")
    if report.header_bundle_sha256 != header_bundle_sha256(headers):
        raise ValueError("header mapping content does not match report header_bundle_sha256")


def _validate_rendered_artifact(
    artifact: SourceArtifactMetadata,
    method_id: str,
    includes: tuple[str, ...],
    rendered: dict[Path, RenderedContent] | None,
) -> None:
    if artifact.method_id != method_id:
        raise ValueError(f"artifact method id mismatch: {artifact.method_id} != {method_id}")
    if artifact.header_includes != includes:
        raise ValueError(f"artifact header mapping mismatch for {method_id}")
    descriptors = tuple(artifact.artifacts)
    if rendered is None:
        if descriptors:
            raise ValueError(f"artifact descriptors have no rendered files for {method_id}")
        return
    rendered_by_path = _normalized_rendered_files(rendered)
    descriptor_by_path = _normalized_descriptors(descriptors)
    if set(rendered_by_path) != set(descriptor_by_path):
        raise ValueError(f"rendered artifacts do not match descriptors for {method_id}")
    _validate_artifact_hashes(rendered_by_path, descriptor_by_path)


def _normalized_rendered_files(rendered: dict[Path, RenderedContent]) -> dict[str, RenderedContent]:
    files: dict[str, RenderedContent] = {}
    for relative_path, content in rendered.items():
        normalized = _relative_path(safe_relative_path(relative_path))
        if normalized in files:
            raise ValueError(f"duplicate rendered artifact path: {normalized}")
        files[normalized] = content
    return files


def _normalized_descriptors(
    descriptors: tuple[ArtifactDescriptor, ...],
) -> dict[str, ArtifactDescriptor]:
    result: dict[str, ArtifactDescriptor] = {}
    for descriptor in descriptors:
        normalized = _relative_path(safe_relative_path(Path(descriptor.path)))
        if normalized in result:
            raise ValueError(f"duplicate artifact descriptor path: {normalized}")
        if not descriptor.kind or not re.fullmatch(r"[0-9a-f]{64}", descriptor.sha256):
            raise ValueError(f"invalid artifact descriptor for {normalized}")
        result[normalized] = descriptor
    return result


def _validate_artifact_hashes(
    rendered: dict[str, RenderedContent], descriptors: dict[str, ArtifactDescriptor]
) -> None:
    for relative_path, content in rendered.items():
        descriptor = descriptors[relative_path]
        if descriptor.sha256 != content_sha256(content):
            raise ValueError(f"artifact hash mismatch for {relative_path}")
        if descriptor.byte_length is not None:
            actual_length = len(content if isinstance(content, bytes) else content.encode("utf-8"))
            if descriptor.byte_length != actual_length:
                raise ValueError(f"artifact byte length mismatch for {relative_path}")


def _header_includes(
    report: ImplementationDiscoveryReport,
    symbol: str,
    headers: Mapping[str, str],
) -> tuple[str, ...]:
    available = tuple(headers) if headers else tuple(report.header_files)
    candidates = (
        create_header_filename(symbol),
        create_header_filename(symbol.rsplit("::", 1)[-1]),
    )
    selected = tuple(candidate for candidate in candidates if candidate in available)
    if selected:
        return (selected[0],)
    return available if not headers and len(available) == 1 else ()


def _bind_header_manifest(
    report: ImplementationDiscoveryReport,
    output_root: Path,
    platform: ELFPlatform,
) -> ImplementationDiscoveryReport:
    manifest_path = (
        output_root / platform.value / AtomicImplementationReportPublisher.HEADER_MANIFEST_NAME
    )
    if not manifest_path.exists():
        return report
    return replace(report, header_manifest_sha256=sha256_file(manifest_path))


def _without_sources(report: ImplementationDiscoveryReport) -> ImplementationDiscoveryReport:
    return replace(
        report,
        methods=tuple(replace(method, source_artifact=None) for method in report.methods),
        source_status="not_requested",
    )


def _commit_bundle_and_report(
    stage: Path | None,
    bundle_target: Path,
    report_target: Path,
    report: ImplementationDiscoveryReport,
) -> None:
    report_payload = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    report_temporary: Path | None = temporary_text(report_target, report_payload)
    bundle_backup: Path | None = None
    report_backup: Path | None = None
    bundle_published = False
    report_published = False
    try:
        if stage is not None:
            _write_bundle_manifest(stage, report, report_target.name, report_payload)
        bundle_backup = _backup_target(bundle_target, "bundle")
        report_backup = _backup_target(report_target, "report")
        if stage is not None:
            os.replace(stage, bundle_target)
            bundle_published = True
        if report_temporary is None:
            raise RuntimeError("report temporary was unexpectedly consumed")
        os.replace(report_temporary, report_target)
        report_temporary = None
        report_published = True
    except Exception:
        _rollback_commit(
            report_temporary,
            bundle_target,
            bundle_backup,
            bundle_published,
            report_target,
            report_backup,
            report_published,
        )
        raise
    finally:
        _discard_backup(bundle_backup)
        _discard_backup(report_backup)


def _write_bundle_manifest(
    stage: Path,
    report: ImplementationDiscoveryReport,
    report_filename: str,
    report_payload: str,
) -> None:
    files = _bundle_files(stage)
    _validate_bundle_consistency(stage, report, files)
    manifest = {
        "schema_version": AtomicImplementationReportPublisher.BUNDLE_SCHEMA_VERSION,
        "artifact_profile": report.artifact_profile.value,
        "root_symbol": report.root_symbol,
        "report_path": (Path("..") / report_filename).as_posix(),
        "report_sha256": sha256_text(report_payload),
        "header_bundle_sha256": report.header_bundle_sha256,
        "header_manifest_sha256": report.header_manifest_sha256,
        "elf_sha256": report.elf_sha256,
        "bundle_sha256": _bundle_digest(files),
        "file_count": len(files),
        "publication_status": report.source_status,
    }
    _write_text(
        stage / AtomicImplementationReportPublisher.BUNDLE_MANIFEST_NAME,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )


def _validate_bundle_consistency(
    stage: Path,
    report: ImplementationDiscoveryReport,
    files: tuple[tuple[str, str], ...],
) -> None:
    expected = tuple(
        sorted(
            (descriptor.path, descriptor.sha256)
            for method in report.methods
            if method.source_artifact is not None
            for descriptor in method.source_artifact.artifacts
        )
    )
    expected_by_path = dict(expected)
    actual_by_path = dict(files)
    if len(expected_by_path) != len(expected) or expected_by_path != actual_by_path:
        missing = sorted(set(expected_by_path) - set(actual_by_path))
        unexpected = sorted(set(actual_by_path) - set(expected_by_path))
        hash_mismatches = sorted(
            path
            for path in set(expected_by_path) & set(actual_by_path)
            if expected_by_path[path] != actual_by_path[path]
        )
        raise ValueError(
            "source bundle files do not match report artifact descriptors"
            f" (expected={len(expected)}, actual={len(files)},"
            f" missing={missing[:5]}, unexpected={unexpected[:5]},"
            f" hash_mismatches={hash_mismatches[:5]})"
        )


def _bundle_files(root: Path) -> tuple[tuple[str, str], ...]:
    files: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _relative_path(path.relative_to(root))
        if relative == AtomicImplementationReportPublisher.BUNDLE_MANIFEST_NAME:
            continue
        files.append((relative, sha256_file(path)))
    return tuple(files)


def _bundle_digest(files: tuple[tuple[str, str], ...]) -> str:
    digest = hashlib.sha256()
    for relative, sha256 in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _backup_target(target: Path, kind: str) -> Path | None:
    if not target.exists():
        return None
    backup = target.parent / f".{target.name}.backup-{kind}-{uuid4().hex}"
    os.replace(target, backup)
    return backup


def _rollback_commit(
    report_temporary: Path | None,
    bundle_target: Path,
    bundle_backup: Path | None,
    bundle_published: bool,
    report_target: Path,
    report_backup: Path | None,
    report_published: bool,
) -> None:
    if report_temporary is not None:
        report_temporary.unlink(missing_ok=True)
    if bundle_published and bundle_target.exists():
        shutil.rmtree(bundle_target, ignore_errors=True)
    if bundle_backup is not None and not bundle_target.exists():
        os.replace(bundle_backup, bundle_target)
    if report_published and report_target.exists():
        report_target.unlink(missing_ok=True)
    if report_backup is not None and not report_target.exists():
        os.replace(report_backup, report_target)


def _discard_backup(backup: Path | None) -> None:
    if backup is None:
        return
    if backup.is_dir():
        shutil.rmtree(backup, ignore_errors=True)
    else:
        backup.unlink(missing_ok=True)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_content(path: Path, content: RenderedContent) -> None:
    if isinstance(content, bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return
    _write_text(path, content)


def _relative_path(path: Path) -> str:
    return path.as_posix()


def _safe_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", symbol).strip("._-") or "symbol"

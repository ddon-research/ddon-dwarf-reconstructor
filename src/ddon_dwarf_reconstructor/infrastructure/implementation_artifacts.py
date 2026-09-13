"""Rendering and enrichment of deterministic implementation method artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from ..domain.models.implementation_context import ImplementationContextEnrichment
from ..domain.models.implementation_evidence import (
    ArtifactDescriptor,
    ImplementationDiscoveryReport,
    ImplementationStatus,
    MethodAssemblyEvidence,
    SourceArtifactMetadata,
)
from .implementation_assembler import assemble_canonical_source
from .implementation_assembly_source import canonical_assembly_source
from .implementation_context import (
    normalize_assembly_export,
    render_context_packet,
)

RenderedContent = str | bytes


def render_canonical_method_artifact(
    method: MethodAssemblyEvidence,
    includes: tuple[str, ...],
    method_id: str,
    assembler: Path | None,
) -> tuple[SourceArtifactMetadata, dict[Path, RenderedContent] | None]:
    """Render raw evidence, canonical assembly, and an optional target object."""
    if not _eligible(method):
        return _not_eligible_artifact(method, includes, method_id)
    return _render_eligible_artifact(method, includes, method_id, assembler)


def _not_eligible_artifact(
    method: MethodAssemblyEvidence,
    includes: tuple[str, ...],
    method_id: str,
) -> tuple[SourceArtifactMetadata, None]:
    return (
        SourceArtifactMetadata(
            method_id=method_id,
            generation_status="not_eligible",
            header_includes=includes,
            diagnostics=(_eligibility_reason(method),),
        ),
        None,
    )


def _render_eligible_artifact(
    method: MethodAssemblyEvidence,
    includes: tuple[str, ...],
    method_id: str,
    assembler: Path | None,
) -> tuple[SourceArtifactMetadata, dict[Path, RenderedContent]]:
    assembly, assembly_diagnostics = canonical_assembly_source(
        method_id,
        method.instructions,
        expected_start=method.selected_function_address,
        expected_size=method.selected_function_size,
    )
    if assembly is None:
        return (
            SourceArtifactMetadata(
                method_id=method_id,
                generation_status="partial",
                header_includes=includes,
                diagnostics=assembly_diagnostics,
            ),
            {},
        )
    rendered, descriptors, object_diagnostics = _render_files(
        method,
        method_id,
        assembly,
        assembler,
    )
    return (
        SourceArtifactMetadata(
            method_id=method_id,
            generation_status="generated",
            header_includes=includes,
            artifacts=tuple(descriptors),
            diagnostics=object_diagnostics,
        ),
        rendered,
    )


def _render_files(
    method: MethodAssemblyEvidence,
    method_id: str,
    assembly: str,
    assembler: Path | None,
) -> tuple[dict[Path, RenderedContent], list[ArtifactDescriptor], tuple[str, ...]]:
    method_dir = Path("methods") / method_id
    rendered: dict[Path, RenderedContent] = {}
    descriptors: list[ArtifactDescriptor] = []
    raw_assembly = normalize_assembly_export(method.raw_disassembly)
    if raw_assembly:
        _add_rendered(
            rendered,
            descriptors,
            "raw-assembly",
            method_dir / f"{method_id}.raw.asm",
            raw_assembly,
            role="source-evidence",
            content_type="text/plain; charset=utf-8",
            producer="orbis-objdump",
        )
    _add_rendered(
        rendered,
        descriptors,
        "canonical-assembly",
        method_dir / f"{method_id}.s",
        assembly,
        role="compiler-input",
        content_type="text/x-asm; charset=utf-8",
        producer="ddon-canonical-byte-assembler",
    )
    object_bytes, object_diagnostics = assemble_canonical_source(method_id, assembly, assembler)
    if object_bytes is not None:
        _add_rendered(
            rendered,
            descriptors,
            "object",
            method_dir / f"{method_id}.o",
            object_bytes,
            role="accepted-object",
            content_type="application/x-elf; charset=binary",
            producer="orbis-as",
        )
    return rendered, descriptors, object_diagnostics


def _add_rendered(
    rendered: dict[Path, RenderedContent],
    descriptors: list[ArtifactDescriptor],
    kind: str,
    path: Path,
    content: RenderedContent,
    *,
    role: str,
    content_type: str,
    producer: str,
) -> None:
    rendered[path] = content
    descriptors.append(
        _descriptor(
            kind,
            path,
            content,
            role=role,
            content_type=content_type,
            producer=producer,
        )
    )


def add_context_artifact(
    method: MethodAssemblyEvidence,
    method_id: str,
    report: ImplementationDiscoveryReport,
    artifact: SourceArtifactMetadata,
    rendered: dict[Path, RenderedContent] | None,
    enrichment: ImplementationContextEnrichment | None = None,
    assembler: Path | None = None,
) -> tuple[SourceArtifactMetadata, dict[Path, RenderedContent] | None]:
    """Append one context packet after the other method files are known."""
    if rendered is None:
        return artifact, None
    object_content = next(
        (
            content
            for path, content in rendered.items()
            if path.as_posix().endswith(f"/{method_id}.o") and isinstance(content, bytes)
        ),
        None,
    )
    context_path = Path("methods") / method_id / f"{method_id}.context.json"
    context = render_context_packet(
        method,
        method_id,
        report,
        artifact.artifacts,
        enrichment=enrichment,
        assembler=assembler,
        object_content=object_content,
    )
    rendered[context_path] = context
    context_descriptor = _descriptor(
        "context",
        context_path,
        context,
        role="ai-transformation-context",
        content_type="application/json; charset=utf-8",
        producer="ddon-implementation-context",
    )
    return replace(artifact, artifacts=(*artifact.artifacts, context_descriptor)), rendered


def _descriptor(
    kind: str,
    path: Path,
    content: RenderedContent,
    *,
    role: str,
    content_type: str,
    producer: str,
) -> ArtifactDescriptor:
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    return ArtifactDescriptor(
        kind=kind,
        path=path.as_posix(),
        sha256=hashlib.sha256(raw).hexdigest(),
        role=role,
        content_type=content_type,
        byte_length=len(raw),
        producer=producer,
    )


def _eligible(method: MethodAssemblyEvidence) -> bool:
    return _is_matched(method) and _has_unique_range(method) and _is_renderable(method)


def _is_matched(method: MethodAssemblyEvidence) -> bool:
    return (
        method.implementation_status is ImplementationStatus.MATCHED
        and method.assembly_status is ImplementationStatus.MATCHED
    )


def _has_unique_range(method: MethodAssemblyEvidence) -> bool:
    return (
        len(method.candidates) == 1
        and method.selected_implementation_die_offset is not None
        and method.selected_function_address is not None
        and method.selected_function_size is not None
        and method.selected_function_size > 0
    )


def _is_renderable(method: MethodAssemblyEvidence) -> bool:
    return bool(
        method.instructions
        and not method.is_deleted
        and not method.is_defaulted
        and not method.is_pure_virtual
    )


def _eligibility_reason(method: MethodAssemblyEvidence) -> str:
    if method.is_deleted or method.is_defaulted or method.is_pure_virtual:
        return "deleted, defaulted, or pure-virtual declaration"
    if method.implementation_status is not ImplementationStatus.MATCHED:
        return f"implementation status is {method.implementation_status.value}"
    if method.assembly_status is not ImplementationStatus.MATCHED:
        return f"assembly status is {method.assembly_status.value}"
    if not method.instructions:
        return "no decoded instructions"
    if len(method.candidates) != 1 or method.selected_implementation_die_offset is None:
        return "implementation candidate is not unique"
    return "definition signature or function range is incomplete"


__all__ = [
    "RenderedContent",
    "add_context_artifact",
    "render_canonical_method_artifact",
]

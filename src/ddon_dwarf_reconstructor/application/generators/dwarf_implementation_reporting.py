"""Canonical implementation-report projection helpers."""

from __future__ import annotations

from dataclasses import replace

from ...domain.models.disassembly import OrbisDisassemblyReport
from ...domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
    MethodAssemblyEvidence,
)
from .generation_contracts import HeaderBundle


def implementation_report(
    root_symbol: str,
    header_bundle: HeaderBundle,
    status: ImplementationStatus,
    methods: tuple[MethodAssemblyEvidence, ...],
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
    elf_sha256: str | None,
) -> ImplementationDiscoveryReport:
    """Build the report without copying detailed evidence into method artifacts."""
    diagnostics = (
        *(disassembly.diagnostics if disassembly else ()),
        *((disassembly_error,) if disassembly_error else ()),
    )
    report = ImplementationDiscoveryReport(
        root_symbol,
        header_bundle.sha256,
        status,
        methods,
        diagnostics=diagnostics,
        header_files=tuple(header_bundle.headers),
        elf_sha256=elf_sha256,
    )
    return _with_disassembly_evidence(report, disassembly) if disassembly else report


def _with_disassembly_evidence(
    report: ImplementationDiscoveryReport, disassembly: OrbisDisassemblyReport
) -> ImplementationDiscoveryReport:
    """Project the Orbis report into the typed implementation-report fields."""
    return replace(
        report,
        disassembly_artifact_key=disassembly.artifact_key,
        elf_sha256=disassembly.elf_sha256,
        tool=disassembly.tool,
        tool_invocations=disassembly.invocations,
        standard_relocations=disassembly.relocations,
        dynamic_tags=disassembly.dynamic_tags,
        relocation_tables=disassembly.relocation_tables,
        relocation_entries=disassembly.relocation_entries,
        relocation_cache_path=disassembly.relocation_cache_path,
        relocation_cache_sha256=disassembly.relocation_cache_sha256,
        relocation_cache_entry_count=disassembly.relocation_cache_entry_count,
        sce_metadata_status=disassembly.sce_metadata_status,
        sce_metadata_diagnostics=disassembly.sce_metadata_diagnostics,
        llvm_cross_check=disassembly.llvm_cross_check,
        llvm_targeted_cross_check=disassembly.llvm_targeted_cross_check,
        sdk_definition_identity=disassembly.sdk_definition_identity,
    )


__all__ = ["implementation_report"]

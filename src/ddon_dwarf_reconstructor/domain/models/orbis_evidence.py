"""Shared projection of additive Orbis evidence into typed report models."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .disassembly import (
    OrbisDisassemblyReport,
    OrbisDynamicTag,
    OrbisReference,
    OrbisRelocationEntry,
    OrbisRelocationTable,
    OrbisSdkDefinitionIdentity,
    OrbisStructuralCrossCheck,
    OrbisTargetedDisassemblyCrossCheck,
    OrbisToolIdentity,
    OrbisToolInvocation,
)
from .implementation_evidence import ImplementationDiscoveryReport


@dataclass(frozen=True, slots=True)
class OrbisEvidenceProjection:
    """Fields shared by disassembly and implementation evidence reports."""

    artifact_key: str
    elf_sha256: str
    tool: OrbisToolIdentity
    tool_invocations: tuple[OrbisToolInvocation, ...]
    standard_relocations: tuple[OrbisReference, ...]
    dynamic_tags: tuple[OrbisDynamicTag, ...]
    relocation_tables: tuple[OrbisRelocationTable, ...]
    relocation_entries: tuple[OrbisRelocationEntry, ...]
    relocation_cache_path: str | None
    relocation_cache_sha256: str | None
    relocation_cache_entry_count: int | None
    sce_metadata_status: str
    sce_metadata_diagnostics: tuple[str, ...]
    llvm_cross_check: OrbisStructuralCrossCheck | None
    llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None

    @classmethod
    def from_report(cls, report: OrbisDisassemblyReport) -> OrbisEvidenceProjection:
        """Extract the stable shared fields without copying report internals."""
        return cls(
            artifact_key=report.artifact_key,
            elf_sha256=report.elf_sha256,
            tool=report.tool,
            tool_invocations=report.invocations,
            standard_relocations=report.relocations,
            dynamic_tags=report.dynamic_tags,
            relocation_tables=report.relocation_tables,
            relocation_entries=report.relocation_entries,
            relocation_cache_path=report.relocation_cache_path,
            relocation_cache_sha256=report.relocation_cache_sha256,
            relocation_cache_entry_count=report.relocation_cache_entry_count,
            sce_metadata_status=report.sce_metadata_status,
            sce_metadata_diagnostics=report.sce_metadata_diagnostics,
            llvm_cross_check=report.llvm_cross_check,
            llvm_targeted_cross_check=report.llvm_targeted_cross_check,
            sdk_definition_identity=report.sdk_definition_identity,
        )

    def apply_to_implementation(
        self, report: ImplementationDiscoveryReport
    ) -> ImplementationDiscoveryReport:
        """Project Orbis fields into the flattened implementation wire model."""
        return replace(
            report,
            disassembly_artifact_key=self.artifact_key,
            elf_sha256=self.elf_sha256,
            tool=self.tool,
            tool_invocations=self.tool_invocations,
            standard_relocations=self.standard_relocations,
            dynamic_tags=self.dynamic_tags,
            relocation_tables=self.relocation_tables,
            relocation_entries=self.relocation_entries,
            relocation_cache_path=self.relocation_cache_path,
            relocation_cache_sha256=self.relocation_cache_sha256,
            relocation_cache_entry_count=self.relocation_cache_entry_count,
            sce_metadata_status=self.sce_metadata_status,
            sce_metadata_diagnostics=self.sce_metadata_diagnostics,
            llvm_cross_check=self.llvm_cross_check,
            llvm_targeted_cross_check=self.llvm_targeted_cross_check,
            sdk_definition_identity=self.sdk_definition_identity,
        )


__all__ = ["OrbisEvidenceProjection"]

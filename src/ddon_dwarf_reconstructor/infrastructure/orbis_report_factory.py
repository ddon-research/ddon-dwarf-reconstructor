"""Single construction boundary for flattened Orbis disassembly reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ..domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisDynamicTag,
    OrbisFunctionDisassembly,
    OrbisReference,
    OrbisRelocationEntry,
    OrbisRelocationTable,
    OrbisSceSegment,
    OrbisSdkDefinitionIdentity,
    OrbisStructuralCrossCheck,
    OrbisTargetedDisassemblyCrossCheck,
    OrbisToolIdentity,
    OrbisToolInvocation,
)
from .orbis_objdump_profiles import DISASSEMBLY_FLAGS, PARSER_VERSION, REPORT_SCHEMA_VERSION

if TYPE_CHECKING:
    from .orbis_sce_metadata import SceMetadataReadResult


class ReportContext(Protocol):
    """The normalized context required by both report construction paths."""

    @property
    def artifact_key(self) -> str: ...

    @property
    def root_symbol(self) -> str: ...

    @property
    def elf_sha256(self) -> str: ...

    @property
    def tool(self) -> OrbisToolIdentity: ...

    @property
    def sdk_definition_identity(self) -> OrbisSdkDefinitionIdentity | None: ...

    @property
    def scope_hash(self) -> str | None: ...

    @property
    def scope_policy(self) -> str: ...

    @property
    def target_count(self) -> int: ...


@dataclass(frozen=True, slots=True)
class OrbisReportEvidence:
    """Additional profiles projected into the report wire model."""

    standard_relocations: tuple[OrbisReference, ...]
    dynamic_tags: tuple[OrbisDynamicTag, ...]
    sce_segments: tuple[OrbisSceSegment, ...]
    relocation_tables: tuple[OrbisRelocationTable, ...]
    relocation_entries: tuple[OrbisRelocationEntry, ...]
    relocation_cache_path: str | None
    relocation_cache_sha256: str | None
    relocation_cache_entry_count: int | None
    sce_metadata_status: str
    sce_metadata_diagnostics: tuple[str, ...]
    llvm_cross_check: OrbisStructuralCrossCheck | None
    llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None

    @classmethod
    def from_profiles(
        cls,
        standard_relocations: tuple[OrbisReference, ...],
        sce_metadata: SceMetadataReadResult,
        llvm_cross_check: OrbisStructuralCrossCheck | None,
        llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None,
        relocation_entries: tuple[OrbisRelocationEntry, ...] = (),
    ) -> OrbisReportEvidence:
        return cls(
            standard_relocations=standard_relocations,
            dynamic_tags=sce_metadata.dynamic_tags,
            sce_segments=sce_metadata.sce_segments,
            relocation_tables=sce_metadata.relocation_tables,
            relocation_entries=relocation_entries,
            relocation_cache_path=sce_metadata.cache_path,
            relocation_cache_sha256=sce_metadata.cache_sha256,
            relocation_cache_entry_count=sce_metadata.cache_entry_count,
            sce_metadata_status=sce_metadata.status,
            sce_metadata_diagnostics=sce_metadata.diagnostics,
            llvm_cross_check=llvm_cross_check,
            llvm_targeted_cross_check=llvm_targeted_cross_check,
        )


def empty_disassembly_report(
    context: ReportContext,
    invocations: list[OrbisToolInvocation],
    diagnostics: tuple[str, ...],
) -> OrbisDisassemblyReport:
    """Build the empty report used when symbol discovery has no candidates."""
    return OrbisDisassemblyReport(
        artifact_key=context.artifact_key,
        build_root=context.root_symbol,
        elf_sha256=context.elf_sha256,
        tool=context.tool,
        flags=DISASSEMBLY_FLAGS,
        parser_version=PARSER_VERSION,
        functions=(),
        schema_version=REPORT_SCHEMA_VERSION,
        invocations=tuple(invocations),
        diagnostics=diagnostics,
        status=(
            "unavailable"
            if any(item.status == "unavailable" for item in invocations)
            else "not_observed"
        ),
        sdk_definition_identity=context.sdk_definition_identity,
        scope_hash=context.scope_hash,
        scope_policy=context.scope_policy,
        target_count=context.target_count,
    )


def build_disassembly_report(
    context: ReportContext,
    functions: tuple[OrbisFunctionDisassembly, ...],
    invocations: list[OrbisToolInvocation],
    evidence: OrbisReportEvidence,
    diagnostics: tuple[str, ...],
) -> OrbisDisassemblyReport:
    """Build the full report from already-normalized profile evidence."""
    statuses = {invocation.status for invocation in invocations}
    if evidence.sce_metadata_status != "observed":
        statuses.add(evidence.sce_metadata_status)
    return OrbisDisassemblyReport(
        artifact_key=context.artifact_key,
        build_root=context.root_symbol,
        elf_sha256=context.elf_sha256,
        tool=context.tool,
        flags=DISASSEMBLY_FLAGS,
        parser_version=PARSER_VERSION,
        functions=functions,
        schema_version=REPORT_SCHEMA_VERSION,
        invocations=tuple(invocations),
        relocations=evidence.standard_relocations,
        dynamic_tags=evidence.dynamic_tags,
        sce_segments=evidence.sce_segments,
        relocation_tables=evidence.relocation_tables,
        relocation_entries=evidence.relocation_entries,
        relocation_cache_path=evidence.relocation_cache_path,
        relocation_cache_sha256=evidence.relocation_cache_sha256,
        relocation_cache_entry_count=evidence.relocation_cache_entry_count,
        sce_metadata_status=evidence.sce_metadata_status,
        sce_metadata_diagnostics=evidence.sce_metadata_diagnostics,
        llvm_cross_check=evidence.llvm_cross_check,
        llvm_targeted_cross_check=evidence.llvm_targeted_cross_check,
        sdk_definition_identity=context.sdk_definition_identity,
        diagnostics=tuple((*diagnostics, *evidence.sce_metadata_diagnostics)),
        status="partial" if statuses - {"observed"} else "observed",
        scope_hash=context.scope_hash,
        scope_policy=context.scope_policy,
        target_count=context.target_count,
    )


__all__ = [
    "OrbisReportEvidence",
    "build_disassembly_report",
    "empty_disassembly_report",
]

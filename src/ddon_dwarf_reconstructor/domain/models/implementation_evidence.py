"""Source-bound method implementation and assembly evidence contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import cast

from .disassembly import (
    OrbisDynamicTag,
    OrbisInstruction,
    OrbisReference,
    OrbisRelocationEntry,
    OrbisRelocationTable,
    OrbisSdkDefinitionIdentity,
    OrbisStructuralCrossCheck,
    OrbisTargetedDisassemblyCrossCheck,
    OrbisToolIdentity,
    OrbisToolInvocation,
)
from .disassembly_scope import DisassemblyTarget
from .implementation_validation import MethodContextPacket

_OptionalEvidenceModel = (
    OrbisToolIdentity
    | OrbisStructuralCrossCheck
    | OrbisTargetedDisassemblyCrossCheck
    | OrbisSdkDefinitionIdentity
)


def _asdict_or_none(value: _OptionalEvidenceModel | None) -> dict[str, object] | None:
    if value is None:
        return None
    return cast(dict[str, object], asdict(value))


class ImplementationStatus(StrEnum):
    """Explicit outcomes for bounded implementation and assembly discovery."""

    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    NOT_OBSERVED = "not_observed"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"


class ImplementationArtifactProfile(StrEnum):
    """Published implementation views supported by the canonical output."""

    CANONICAL_ASSEMBLY = "canonical-assembly"


class ImplementationRelation(StrEnum):
    """DWARF relationship used to reach an implementation DIE."""

    DIRECT = "direct"
    SPECIFICATION = "specification"
    ABSTRACT_ORIGIN = "abstract_origin"


class FunctionMatchKind(StrEnum):
    """Reason a disassembled ELF function was associated with a DWARF target."""

    RANGE_START = "range_start"
    RANGE_CONTAINED = "range_contained"
    LINKAGE_NAME = "linkage_name"
    QUALIFIED_NAME = "qualified_name"
    AMBIGUOUS = "ambiguous"
    SCOPE_MISSING = "scope_missing"


@dataclass(frozen=True, slots=True)
class CodeRange:
    """One validated half-open machine-code range from DWARF."""

    start_address: int
    end_address: int
    source: str

    def __post_init__(self) -> None:
        max_address = (1 << 64) - 1
        if not (
            isinstance(self.start_address, int)
            and not isinstance(self.start_address, bool)
            and isinstance(self.end_address, int)
            and not isinstance(self.end_address, bool)
            and 0 <= self.start_address < self.end_address < max_address
            and self.start_address != max_address
            and self.end_address != max_address
        ):
            raise ValueError(
                "CodeRange requires a positive half-open interval inside the 64-bit address domain"
            )

    def overlaps(self, start_address: int, end_address: int) -> bool:
        """Return whether another half-open interval overlaps this range."""
        return self.start_address < end_address and start_address < self.end_address

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MethodImplementationCandidate:
    """One declaration-to-implementation association with range evidence."""

    declaration_die_offset: int
    implementation_die_offset: int
    declaration_cu_offset: int | None
    implementation_cu_offset: int | None
    relation: ImplementationRelation
    name: str | None
    linkage_name: str | None
    code_ranges: tuple[CodeRange, ...] = ()
    is_inline: bool | None = None
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["relation"] = self.relation.value
        payload["code_ranges"] = [item.to_dict() for item in self.code_ranges]
        return payload


@dataclass(frozen=True, slots=True)
class MethodAssemblyEvidence:
    """Assembly evidence for one header-discovered method."""

    owner: str
    method_name: str
    signature: str
    declaration_die_offset: int | None
    declaration_cu_offset: int | None
    implementation_status: ImplementationStatus
    assembly_status: ImplementationStatus
    candidates: tuple[MethodImplementationCandidate, ...] = ()
    selected_implementation_die_offset: int | None = None
    selected_function_name: str | None = None
    selected_function_address: int | None = None
    selected_function_size: int | None = None
    instructions: tuple[OrbisInstruction, ...] = ()
    diagnostics: tuple[str, ...] = ()
    definition_signature: str | None = None
    raw_disassembly: str = ""
    relocation_ids: tuple[str, ...] = ()
    dwarf_context: MethodContextPacket | None = None
    source_artifact: SourceArtifactMetadata | None = None
    assembly_function_candidates: tuple[FunctionAssociationCandidate, ...] = ()
    assembly_match_reasons: tuple[FunctionMatchKind, ...] = ()
    is_deleted: bool = False
    is_defaulted: bool = False
    is_pure_virtual: bool = False

    @property
    def references(self) -> tuple[OrbisReference, ...]:
        """Return instruction references as a derived convenience view."""
        return tuple(
            reference for instruction in self.instructions for reference in instruction.references
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["implementation_status"] = self.implementation_status.value
        payload["assembly_status"] = self.assembly_status.value
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        payload["instructions"] = [
            _instruction_to_dict(instruction) for instruction in self.instructions
        ]
        payload["source_artifact"] = (
            self.source_artifact.to_dict() if self.source_artifact is not None else None
        )
        payload["dwarf_context"] = (
            self.dwarf_context.to_dict() if self.dwarf_context is not None else None
        )
        payload["assembly_function_candidates"] = [
            item.to_dict() for item in self.assembly_function_candidates
        ]
        payload["assembly_match_reasons"] = [item.value for item in self.assembly_match_reasons]
        return payload


@dataclass(frozen=True, slots=True)
class FunctionAssociationCandidate:
    """One ELF function candidate retained during method association."""

    address: int
    size: int
    name: str
    match_kind: FunctionMatchKind
    selected: bool = False
    implementation_die_offset: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["match_kind"] = self.match_kind.value
        return payload


@dataclass(frozen=True, slots=True)
class SourceArtifactMetadata:
    """Published derived artifacts for one generated reconstruction method."""

    method_id: str
    generation_status: str
    header_includes: tuple[str, ...] = ()
    artifacts: tuple[ArtifactDescriptor, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "method_id": self.method_id,
            "generation_status": self.generation_status,
            "header_includes": list(self.header_includes),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    """One typed, content-addressed derived artifact."""

    kind: str
    path: str
    sha256: str
    role: str = "derived"
    content_type: str = "application/octet-stream"
    byte_length: int | None = None
    producer: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "role": self.role,
            "content_type": self.content_type,
            "byte_length": self.byte_length,
            "producer": self.producer,
        }


@dataclass(frozen=True, slots=True)
class EvidenceLimitation:
    """A structured boundary on what implementation evidence can establish."""

    code: str
    scope: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "scope": self.scope,
            "message": self.message,
        }


DEFAULT_IMPLEMENTATION_LIMITATIONS = (
    EvidenceLimitation(
        "abi_not_inferred",
        "bundle",
        "Register preservation, clobbers, calling convention, and ABI correctness are not inferred.",
    ),
    EvidenceLimitation(
        "semantic_equivalence_not_validated",
        "bundle",
        "Recovered instructions are evidence and not a behavioral equivalence claim.",
    ),
    EvidenceLimitation(
        "external_declaration_not_synthesized",
        "bundle",
        "External variables and methods remain structured references; no declarations are invented.",
    ),
    EvidenceLimitation(
        "relocation_application_not_validated",
        "bundle",
        "Relocation targets and load-base formulas require the explicit validate-implementation workflow.",
    ),
    EvidenceLimitation(
        "register_stack_safety_not_validated",
        "bundle",
        "The canonical C++ view does not claim register, stack, CFI, or call-site safety.",
    ),
    EvidenceLimitation(
        "orbis_compiler_not_validated",
        "bundle",
        "Header closure and host compilation do not establish Orbis clang/as target acceptance.",
    ),
    EvidenceLimitation(
        "live_behavior_not_observed",
        "bundle",
        "No PS4 execution or behavioral-equivalence harness is assumed by this artifact.",
    ),
)


@dataclass(frozen=True, slots=True)
class ImplementationDiscoveryReport:
    """Separate, source-bound output produced after header generation."""

    root_symbol: str
    header_bundle_sha256: str
    status: ImplementationStatus
    methods: tuple[MethodAssemblyEvidence, ...]
    disassembly_artifact_key: str | None = None
    elf_sha256: str | None = None
    tool: OrbisToolIdentity | None = None
    diagnostics: tuple[str, ...] = ()
    tool_invocations: tuple[OrbisToolInvocation, ...] = ()
    standard_relocations: tuple[OrbisReference, ...] = ()
    dynamic_tags: tuple[OrbisDynamicTag, ...] = ()
    relocation_tables: tuple[OrbisRelocationTable, ...] = ()
    relocation_entries: tuple[OrbisRelocationEntry, ...] = ()
    relocation_cache_path: str | None = None
    relocation_cache_sha256: str | None = None
    relocation_cache_entry_count: int | None = None
    sce_metadata_status: str = "not_observed"
    sce_metadata_diagnostics: tuple[str, ...] = ()
    llvm_cross_check: OrbisStructuralCrossCheck | None = None
    llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None = None
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None
    header_files: tuple[str, ...] = ()
    source_status: str = "not_requested"
    header_manifest_sha256: str | None = None
    schema_version: str = "4.2"
    artifact_profile: ImplementationArtifactProfile = (
        ImplementationArtifactProfile.CANONICAL_ASSEMBLY
    )
    disassembly_scope_hash: str | None = None
    disassembly_scope_policy: str = "dwarf-range-closure-v1"
    disassembly_target_manifest: tuple[DisassemblyTarget, ...] = ()
    limitations: tuple[EvidenceLimitation, ...] = DEFAULT_IMPLEMENTATION_LIMITATIONS
    analytical_backend: str | None = None
    analytical_store_manifest_sha256: str | None = None
    analytical_store_schema_version: str | None = None
    analytical_query_policy: str = "read-only-doris"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "artifact_profile": self.artifact_profile.value,
            "root_symbol": self.root_symbol,
            "header_bundle_sha256": self.header_bundle_sha256,
            "header_manifest_sha256": self.header_manifest_sha256,
            "status": self.status.value,
            "methods": [method.to_dict() for method in self.methods],
            "disassembly_artifact_key": self.disassembly_artifact_key,
            "elf_sha256": self.elf_sha256,
            "tool": _asdict_or_none(self.tool),
            "diagnostics": list(self.diagnostics),
            "tool_invocations": [asdict(item) for item in self.tool_invocations],
            "standard_relocations": [asdict(item) for item in self.standard_relocations],
            "dynamic_tags": [asdict(item) for item in self.dynamic_tags],
            "relocation_tables": [asdict(item) for item in self.relocation_tables],
            "relocation_entries": [asdict(item) for item in self.relocation_entries],
            "relocation_cache_path": self.relocation_cache_path,
            "relocation_cache_sha256": self.relocation_cache_sha256,
            "relocation_cache_entry_count": self.relocation_cache_entry_count,
            "sce_metadata_status": self.sce_metadata_status,
            "sce_metadata_diagnostics": list(self.sce_metadata_diagnostics),
            "llvm_cross_check": _asdict_or_none(self.llvm_cross_check),
            "llvm_targeted_cross_check": _asdict_or_none(self.llvm_targeted_cross_check),
            "sdk_definition_identity": _asdict_or_none(self.sdk_definition_identity),
            "header_files": list(self.header_files),
            "source_status": self.source_status,
            "disassembly_scope_hash": self.disassembly_scope_hash,
            "disassembly_scope_policy": self.disassembly_scope_policy,
            "disassembly_target_manifest": [
                item.to_dict() for item in self.disassembly_target_manifest
            ],
            "limitations": [item.to_dict() for item in self.limitations],
            "analytical_backend": self.analytical_backend,
            "analytical_store_manifest_sha256": self.analytical_store_manifest_sha256,
            "analytical_store_schema_version": self.analytical_store_schema_version,
            "analytical_query_policy": self.analytical_query_policy,
        }


def _instruction_to_dict(instruction: OrbisInstruction) -> dict[str, object]:
    """Serialize one instruction without repeating the exact raw source line."""
    payload = asdict(instruction)
    payload.pop("raw_line", None)
    return cast(dict[str, object], payload)


__all__ = [
    "ArtifactDescriptor",
    "CodeRange",
    "DEFAULT_IMPLEMENTATION_LIMITATIONS",
    "EvidenceLimitation",
    "FunctionAssociationCandidate",
    "FunctionMatchKind",
    "ImplementationDiscoveryReport",
    "ImplementationArtifactProfile",
    "ImplementationRelation",
    "ImplementationStatus",
    "MethodAssemblyEvidence",
    "MethodImplementationCandidate",
    "SourceArtifactMetadata",
]

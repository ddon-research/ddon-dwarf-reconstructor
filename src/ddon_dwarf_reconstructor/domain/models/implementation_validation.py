"""Typed evidence contracts for implementation-generation validation.

The implementation-discovery report answers whether a DWARF declaration can be
associated with a machine-code range.  These models describe the additional
questions required before a derived assembly/object artifact can be promoted.
Each dimension keeps its own status so one unavailable tool cannot make a
different evidence dimension appear complete.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum, StrEnum
from typing import Any

from .disassembly import OrbisSdkDefinitionIdentity


class ValidationStatus(StrEnum):
    """Status vocabulary shared by validation dimensions."""

    OBSERVED = "observed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_OBSERVED = "not_observed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class NidResolution(StrEnum):
    """How a NID name was obtained and how far it was independently checked."""

    OPAQUE = "opaque"
    EXPLICIT_SOURCE_BOUND = "explicit_source_bound"
    COMMUNITY_CANDIDATE = "community_candidate"
    COMMUNITY_VERIFIED = "community_verified"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class EvidenceStatus:
    """One independently evaluated status and its bounded diagnostics."""

    status: ValidationStatus
    diagnostics: tuple[str, ...] = ()
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class MappedSegment:
    """One PT_LOAD mapping in both file and selected runtime address spaces."""

    index: int
    flags: int
    file_offset: int
    virtual_address: int
    file_size: int
    memory_size: int
    alignment: int
    runtime_start: int | None
    runtime_file_end: int | None
    runtime_memory_end: int | None

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class LoadImageProfile:
    """Explicit load-bias policy and validation result."""

    policy: str
    requested_base: int | None
    minimum_virtual_address: int | None
    load_bias: int | None
    required_alignment: int | None
    status: ValidationStatus
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class RelocationApplication:
    """Pure evaluation of one relocation without mutating the source ELF."""

    relocation_id: str
    relocation_code: int
    relocation_name: str | None
    relocation_offset: int
    target_runtime_address: int | None
    target_file_offset: int | None
    width_bytes: int | None
    formula: str | None
    addend: int
    symbol_index: int
    symbol_name: str | None
    symbol_value: int | None
    original_bytes: str | None
    evaluated_value: int | None
    evaluated_bytes: str | None
    status: ValidationStatus
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class NidBinding:
    """Opaque or source-bound import/export identity associated with a symbol."""

    relocation_id: str | None
    encoded_symbol: str | None
    encoded_nid: str | None
    module_id: int | None
    library_id: int | None
    version_major: int | None
    version_minor: int | None
    resolved_name: str | None
    source: str | None
    status: ValidationStatus
    diagnostics: tuple[str, ...] = ()
    resolution: NidResolution = NidResolution.OPAQUE
    encoded_library_index: int | None = None
    encoded_module_index: int | None = None
    hash_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    context_status: ValidationStatus = ValidationStatus.NOT_OBSERVED

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class AbiEvidence:
    """Observed ABI facts for one method or one compiler probe."""

    status: ValidationStatus
    target_triple: str | None = None
    calling_convention: str | None = None
    object_pointer: str | None = None
    parameter_locations: tuple[str, ...] = ()
    hidden_parameters: tuple[str, ...] = ()
    artificial_parameters: tuple[str, ...] = ()
    frame_base_locations: tuple[str, ...] = ()
    return_location: str | None = None
    hidden_return: bool | None = None
    stack_alignment: int | None = None
    callee_saved_registers: tuple[str, ...] = ()
    cfi_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class InstructionEffects:
    """Conservative register, flags, memory, and stack summary."""

    status: ValidationStatus
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    flags_read: tuple[str, ...] = ()
    flags_written: tuple[str, ...] = ()
    memory_read: bool | None = None
    memory_write: bool | None = None
    calls: tuple[str, ...] = ()
    indirect_call: bool | None = None
    stack_delta_min: int | None = None
    stack_delta_max: int | None = None
    stack_balanced: bool | None = None
    callee_saved_preserved: bool | None = None
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class CompilerEvidence:
    """One external compiler/assembler acceptance result."""

    status: ValidationStatus
    profile: str | None = None
    tool: str | None = None
    tool_sha256: str | None = None
    version: str | None = None
    command: tuple[str, ...] = ()
    stdout_path: str | None = None
    stderr_path: str | None = None
    output_path: str | None = None
    output_sha256: str | None = None
    object_metadata: dict[str, object] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class AnalyticalModelEvidence:
    """Identity of the analytical query model used by validation."""

    backend: str
    source_id: str
    manifest_sha256: str
    manifest_schema_version: str
    database: str
    table: str
    serving_variant_id: str
    registry_status: str
    query_policy: str = "read-only-doris"

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class SemanticParity:
    """Static parity gates; live execution is deliberately a separate field."""

    status: ValidationStatus
    byte_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    cfg_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    external_edge_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    effect_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    live_behavior_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class MethodContextPacket:
    """One bounded join of DWARF, machine-code, relocation, and diagnostic evidence."""

    declaration_die_offset: int | None
    implementation_die_offset: int | None
    declaration_cu_offset: int | None
    implementation_cu_offset: int | None
    code_ranges: tuple[tuple[int, int, str], ...] = ()
    locations: tuple[dict[str, object], ...] = ()
    cfi: tuple[dict[str, object], ...] = ()
    disassembly_addresses: tuple[int, ...] = ()
    relocation_ids: tuple[str, ...] = ()
    nid_ids: tuple[str, ...] = ()
    abi_facts: dict[str, object] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class MethodValidationEvidence:
    """Independent validation dimensions for one discovered method."""

    method_id: str
    method_name: str
    function_address: int | None
    function_size: int | None
    context: MethodContextPacket
    relocation_status: ValidationStatus
    nid_status: ValidationStatus
    abi: AbiEvidence
    effects: InstructionEffects
    compiler: CompilerEvidence
    parity: SemanticParity
    artifacts: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class ImplementationValidationReport:
    """Source-bound implementation validation bundle."""

    source_path: str
    source_sha256: str
    implementation_report_path: str
    implementation_report_sha256: str
    status: ValidationStatus
    load_image: LoadImageProfile
    segments: tuple[MappedSegment, ...]
    relocations: tuple[RelocationApplication, ...]
    nids: tuple[NidBinding, ...]
    methods: tuple[MethodValidationEvidence, ...]
    compiler: CompilerEvidence
    abi_probes: tuple[CompilerEvidence, ...] = ()
    analytical_model: AnalyticalModelEvidence | None = None
    analytical_store_manifest_sha256: str | None = None
    analytical_store_schema_version: str | None = None
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None
    relocation_evaluator_version: str = "1.0"
    nid_database_identity: str | None = None
    diagnostics: tuple[str, ...] = ()
    schema_version: str = "4.1"
    validation_profile: str = "source-bound-static"

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))


def _jsonable(value: Any) -> Any:
    """Convert nested frozen dataclasses/enums into stable JSON values."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "AnalyticalModelEvidence",
    "AbiEvidence",
    "CompilerEvidence",
    "EvidenceStatus",
    "ImplementationValidationReport",
    "InstructionEffects",
    "LoadImageProfile",
    "MappedSegment",
    "MethodContextPacket",
    "MethodValidationEvidence",
    "NidBinding",
    "NidResolution",
    "RelocationApplication",
    "SemanticParity",
    "ValidationStatus",
]

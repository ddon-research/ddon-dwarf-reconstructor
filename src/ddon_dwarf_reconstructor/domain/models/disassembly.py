"""Typed disassembly evidence models shared across application adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast


@dataclass(frozen=True)
class OrbisToolIdentity:
    """Stable identity and capabilities of one Orbis objdump executable."""

    executable_sha256: str
    version: str
    target: str


@dataclass(frozen=True, slots=True)
class OrbisDefinitionSource:
    """Source package files used to reproduce Sony/Orbis definitions."""

    package: str
    root: str
    files: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True, slots=True)
class OrbisSdkDefinitionIdentity:
    """Typed identity for the SDK-derived PS4 ELF definition subset."""

    version: str
    target_triple: str
    bfd_target: str
    source: OrbisDefinitionSource


@dataclass(frozen=True, slots=True)
class OrbisReference:
    """One resolved or unresolved machine-code reference."""

    kind: str
    address: int | None = None
    resolved_name: str | None = None
    raw_operand: str = ""
    resolution_status: str = "unresolved"
    relocation: str | None = None
    relocation_id: str | None = None


@dataclass(frozen=True, slots=True)
class OrbisDynamicTag:
    """One raw or named SCE dynamic tag from the ELF dynamic section."""

    tag: int
    name: str | None
    value: int


@dataclass(frozen=True, slots=True)
class OrbisSceSegment:
    """One SCE-specific program-header range used for metadata validation."""

    kind: str
    type_code: int
    file_offset: int
    virtual_address: int
    file_size: int
    memory_size: int


@dataclass(frozen=True, slots=True)
class OrbisRelocationTable:
    """Validated descriptor for one PS4/SCE RELA table."""

    name: str
    tag: str
    virtual_address: int | None
    file_offset: int | None
    size: int
    entry_size: int
    count: int
    status: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrbisRelocationEntry:
    """One raw SCE RELA record without applying loader/runtime semantics."""

    relocation_id: str
    table: str
    index: int
    offset: int
    info: int
    addend: int
    symbol_index: int
    relocation_code: int
    relocation_name: str | None
    symbol_name: str | None
    raw_bytes: str
    resolution_status: str
    instruction_addresses: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class OrbisStructuralCrossCheck:
    """Additive generic-ELF evidence retained beside Orbis output."""

    profile: str
    status: str
    output_path: str | None = None
    output_sha256: str | None = None
    unknown_dynamic_tags: tuple[int, ...] = ()
    diagnostics: tuple[str, ...] = ()
    requested_triple: str | None = None
    effective_triple: str | None = None
    target_status: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class OrbisTargetedDisassemblyCrossCheck:
    """Compact comparison summary for one target-aware LLVM profile."""

    profile: str
    requested_triple: str
    effective_triple: str | None
    status: str
    slice_count: int = 0
    observed_slice_count: int = 0
    target_instruction_count: int = 0
    matched_instruction_count: int = 0
    mismatched_instruction_count: int = 0
    cache_keys: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrbisToolInvocation:
    """Retained command evidence for one Orbis profile attempt."""

    profile: str
    command: tuple[str, ...]
    flags: tuple[str, ...]
    return_status: int | None
    status: str
    stdout_path: str | None = None
    stderr_path: str | None = None
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    tool_identity: OrbisToolIdentity | None = None
    duration_ms: float | None = None
    diagnostics: tuple[str, ...] = ()
    cache_key: str | None = None
    requested_triple: str | None = None
    effective_triple: str | None = None
    target_status: str | None = None
    range_start: int | None = None
    range_end: int | None = None


@dataclass(frozen=True)
class OrbisFunctionSymbol:
    """One demangled executable function symbol."""

    address: int
    size: int
    section: str
    name: str

    def __post_init__(self) -> None:
        maximum = 1 << 64
        if (
            isinstance(self.address, bool)
            or not isinstance(self.address, int)
            or isinstance(self.size, bool)
            or not isinstance(self.size, int)
            or self.address < 0
            or self.size <= 0
            or self.address >= maximum
            or self.address + self.size >= maximum - 1
        ):
            raise ValueError("function symbol range is outside the 64-bit address domain")

    @property
    def end_address(self) -> int:
        """Return the half-open end address."""
        return self.address + self.size


@dataclass(frozen=True)
class OrbisInstruction:
    """One decoded instruction with optional source and call evidence."""

    address: int
    raw_bytes: str
    mnemonic: str
    operands: str
    source_file: str | None = None
    source_line: int | None = None
    call_target_address: int | None = None
    call_target_name: str | None = None
    source_discriminator: int | None = None
    raw_source_line: str | None = None
    file_offset: int | None = None
    references: tuple[OrbisReference, ...] = ()
    raw_line: str | None = None


@dataclass(frozen=True)
class OrbisFunctionDisassembly:
    """A bounded function range and every instruction decoded inside it."""

    symbol: OrbisFunctionSymbol
    instructions: tuple[OrbisInstruction, ...]
    raw_text: str = ""


@dataclass(frozen=True)
class OrbisDisassemblyReport:
    """Content-addressed report consumed by deterministic graph export."""

    artifact_key: str
    build_root: str
    elf_sha256: str
    tool: OrbisToolIdentity
    flags: tuple[str, ...]
    parser_version: str
    functions: tuple[OrbisFunctionDisassembly, ...]
    schema_version: str = "2.4"
    invocations: tuple[OrbisToolInvocation, ...] = ()
    relocations: tuple[OrbisReference, ...] = ()
    dynamic_tags: tuple[OrbisDynamicTag, ...] = ()
    sce_segments: tuple[OrbisSceSegment, ...] = ()
    relocation_tables: tuple[OrbisRelocationTable, ...] = ()
    relocation_entries: tuple[OrbisRelocationEntry, ...] = ()
    relocation_cache_path: str | None = None
    relocation_cache_sha256: str | None = None
    relocation_cache_entry_count: int | None = None
    sce_metadata_status: str = "not_observed"
    sce_metadata_diagnostics: tuple[str, ...] = ()
    llvm_cross_check: OrbisStructuralCrossCheck | None = None
    llvm_targeted_cross_check: OrbisTargetedDisassemblyCrossCheck | None = None
    diagnostics: tuple[str, ...] = ()
    status: str = "observed"
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None
    scope_hash: str | None = None
    scope_policy: str = "root-prefix-v1"
    target_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return a stable representation suitable for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> OrbisDisassemblyReport:
        """Restore a cached representation using the shared evidence model."""
        tool_value = cast(dict[str, object], value["tool"])
        function_values = cast(list[dict[str, object]], value["functions"])
        functions = tuple(
            OrbisFunctionDisassembly(
                symbol=_symbol_from_dict(cast(dict[str, object], item["symbol"])),
                instructions=tuple(
                    _instruction_from_dict(instruction)
                    for instruction in cast(list[dict[str, object]], item["instructions"])
                ),
                raw_text=str(item.get("raw_text", "")),
            )
            for item in function_values
        )
        optional_fields = _report_optional_fields(value)
        return cls(
            artifact_key=str(value["artifact_key"]),
            build_root=str(value["build_root"]),
            elf_sha256=str(value["elf_sha256"]),
            tool=OrbisToolIdentity(
                executable_sha256=str(tool_value["executable_sha256"]),
                version=str(tool_value["version"]),
                target=str(tool_value["target"]),
            ),
            flags=tuple(str(flag) for flag in cast(list[object], value["flags"])),
            parser_version=str(value["parser_version"]),
            functions=functions,
            schema_version=str(value.get("schema_version", "2.4")),
            **optional_fields,
            diagnostics=tuple(
                str(item) for item in cast(list[object], value.get("diagnostics", []))
            ),
            status=str(value.get("status", "observed")),
            scope_hash=_optional_string(value.get("scope_hash")),
            scope_policy=str(value.get("scope_policy", "root-prefix-v1")),
            target_count=_required_int(value.get("target_count", 0)),
        )


def _report_optional_fields(value: dict[str, object]) -> dict[str, Any]:
    invocation_values = cast(list[dict[str, object]], value.get("invocations", []))
    relocation_values = cast(list[dict[str, object]], value.get("relocations", []))
    dynamic_tag_values = cast(list[dict[str, object]], value.get("dynamic_tags", []))
    segment_values = cast(list[dict[str, object]], value.get("sce_segments", []))
    table_values = cast(list[dict[str, object]], value.get("relocation_tables", []))
    entry_values = cast(list[dict[str, object]], value.get("relocation_entries", []))
    cross_check_value = value.get("llvm_cross_check")
    return {
        "invocations": tuple(_invocation_from_dict(item) for item in invocation_values),
        "relocations": tuple(_reference_from_dict(item) for item in relocation_values),
        "dynamic_tags": tuple(_dynamic_tag_from_dict(item) for item in dynamic_tag_values),
        "sce_segments": tuple(_segment_from_dict(item) for item in segment_values),
        "relocation_tables": tuple(_table_from_dict(item) for item in table_values),
        "relocation_entries": tuple(_relocation_entry_from_dict(item) for item in entry_values),
        "relocation_cache_path": _optional_string(value.get("relocation_cache_path")),
        "relocation_cache_sha256": _optional_string(value.get("relocation_cache_sha256")),
        "relocation_cache_entry_count": _optional_int(value.get("relocation_cache_entry_count")),
        "sce_metadata_status": str(value.get("sce_metadata_status", "not_observed")),
        "sce_metadata_diagnostics": tuple(
            str(item) for item in cast(list[object], value.get("sce_metadata_diagnostics", []))
        ),
        "llvm_cross_check": (
            _cross_check_from_dict(cast(dict[str, object], cross_check_value))
            if isinstance(cross_check_value, dict)
            else None
        ),
        "llvm_targeted_cross_check": _targeted_cross_check_from_dict(
            value.get("llvm_targeted_cross_check")
        ),
        "sdk_definition_identity": _sdk_definition_identity_from_dict(
            value.get("sdk_definition_identity")
        ),
    }


def _symbol_from_dict(value: dict[str, object]) -> OrbisFunctionSymbol:
    return OrbisFunctionSymbol(
        address=_required_int(value["address"]),
        size=_required_int(value["size"]),
        section=str(value["section"]),
        name=str(value["name"]),
    )


def _instruction_from_dict(value: dict[str, object]) -> OrbisInstruction:
    return OrbisInstruction(
        address=_required_int(value["address"]),
        raw_bytes=str(value["raw_bytes"]),
        mnemonic=str(value["mnemonic"]),
        operands=str(value["operands"]),
        source_file=_optional_string(value.get("source_file")),
        source_line=_optional_int(value.get("source_line")),
        source_discriminator=_optional_int(value.get("source_discriminator")),
        raw_source_line=_optional_string(value.get("raw_source_line")),
        file_offset=_optional_int(value.get("file_offset")),
        call_target_address=_optional_int(value.get("call_target_address")),
        call_target_name=_optional_string(value.get("call_target_name")),
        references=tuple(
            _reference_from_dict(item)
            for item in cast(list[dict[str, object]], value.get("references", []))
        ),
        raw_line=_optional_string(value.get("raw_line")),
    )


def _reference_from_dict(value: dict[str, object]) -> OrbisReference:
    return OrbisReference(
        kind=str(value.get("kind", "unknown")),
        address=_optional_int(value.get("address")),
        resolved_name=_optional_string(value.get("resolved_name")),
        raw_operand=str(value.get("raw_operand", "")),
        resolution_status=str(value.get("resolution_status", "unresolved")),
        relocation=_optional_string(value.get("relocation")),
        relocation_id=_optional_string(value.get("relocation_id")),
    )


def _dynamic_tag_from_dict(value: dict[str, object]) -> OrbisDynamicTag:
    return OrbisDynamicTag(
        tag=_required_int(value.get("tag", 0)),
        name=_optional_string(value.get("name")),
        value=_required_int(value.get("value", 0)),
    )


def _segment_from_dict(value: dict[str, object]) -> OrbisSceSegment:
    return OrbisSceSegment(
        kind=str(value.get("kind", "unknown")),
        type_code=_required_int(value.get("type_code", 0)),
        file_offset=_required_int(value.get("file_offset", 0)),
        virtual_address=_required_int(value.get("virtual_address", 0)),
        file_size=_required_int(value.get("file_size", 0)),
        memory_size=_required_int(value.get("memory_size", 0)),
    )


def _table_from_dict(value: dict[str, object]) -> OrbisRelocationTable:
    return OrbisRelocationTable(
        name=str(value.get("name", "unknown")),
        tag=str(value.get("tag", "unknown")),
        virtual_address=_optional_int(value.get("virtual_address")),
        file_offset=_optional_int(value.get("file_offset")),
        size=_required_int(value.get("size", 0)),
        entry_size=_required_int(value.get("entry_size", 0)),
        count=_required_int(value.get("count", 0)),
        status=str(value.get("status", "unknown")),
        diagnostics=tuple(str(item) for item in cast(list[object], value.get("diagnostics", []))),
    )


def _relocation_entry_from_dict(value: dict[str, object]) -> OrbisRelocationEntry:
    return OrbisRelocationEntry(
        relocation_id=str(value.get("relocation_id", "")),
        table=str(value.get("table", "unknown")),
        index=_required_int(value.get("index", 0)),
        offset=_required_int(value.get("offset", 0)),
        info=_required_int(value.get("info", 0)),
        addend=_required_int(value.get("addend", 0)),
        symbol_index=_required_int(value.get("symbol_index", 0)),
        relocation_code=_required_int(value.get("relocation_code", 0)),
        relocation_name=_optional_string(value.get("relocation_name")),
        symbol_name=_optional_string(value.get("symbol_name")),
        raw_bytes=str(value.get("raw_bytes", "")),
        resolution_status=str(value.get("resolution_status", "unresolved")),
        instruction_addresses=tuple(
            _required_int(item)
            for item in cast(list[object], value.get("instruction_addresses", []))
        ),
    )


def _cross_check_from_dict(value: dict[str, object]) -> OrbisStructuralCrossCheck:
    return OrbisStructuralCrossCheck(
        profile=str(value.get("profile", "unknown")),
        status=str(value.get("status", "unknown")),
        output_path=_optional_string(value.get("output_path")),
        output_sha256=_optional_string(value.get("output_sha256")),
        unknown_dynamic_tags=tuple(
            _required_int(item)
            for item in cast(list[object], value.get("unknown_dynamic_tags", []))
        ),
        diagnostics=tuple(str(item) for item in cast(list[object], value.get("diagnostics", []))),
        requested_triple=_optional_string(value.get("requested_triple")),
        effective_triple=_optional_string(value.get("effective_triple")),
        target_status=str(value.get("target_status", "not_applicable")),
    )


def _sdk_definition_identity_from_dict(
    value: object,
) -> OrbisSdkDefinitionIdentity | None:
    if not isinstance(value, dict):
        return None
    source_value = value.get("source")
    if not isinstance(source_value, dict):
        return None
    files: list[tuple[str, str, int]] = []
    for item in cast(list[object], source_value.get("files", [])):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        files.append((str(item[0]), str(item[1]), _required_int(item[2])))
    return OrbisSdkDefinitionIdentity(
        version=str(value.get("version", "")),
        target_triple=str(value.get("target_triple", "")),
        bfd_target=str(value.get("bfd_target", "")),
        source=OrbisDefinitionSource(
            package=str(source_value.get("package", "")),
            root=str(source_value.get("root", "")),
            files=tuple(files),
        ),
    )


def _targeted_cross_check_from_dict(value: object) -> OrbisTargetedDisassemblyCrossCheck | None:
    if not isinstance(value, dict):
        return None
    return OrbisTargetedDisassemblyCrossCheck(
        profile=str(value.get("profile", "unknown")),
        requested_triple=str(value.get("requested_triple", "")),
        effective_triple=_optional_string(value.get("effective_triple")),
        status=str(value.get("status", "unknown")),
        slice_count=_required_int(value.get("slice_count", 0)),
        observed_slice_count=_required_int(value.get("observed_slice_count", 0)),
        target_instruction_count=_required_int(value.get("target_instruction_count", 0)),
        matched_instruction_count=_required_int(value.get("matched_instruction_count", 0)),
        mismatched_instruction_count=_required_int(value.get("mismatched_instruction_count", 0)),
        cache_keys=tuple(str(item) for item in cast(list[object], value.get("cache_keys", []))),
        diagnostics=tuple(str(item) for item in cast(list[object], value.get("diagnostics", []))),
    )


def _invocation_from_dict(value: dict[str, object]) -> OrbisToolInvocation:
    tool_value = value.get("tool_identity")
    tool = None
    if isinstance(tool_value, dict):
        tool = OrbisToolIdentity(
            executable_sha256=str(tool_value.get("executable_sha256", "")),
            version=str(tool_value.get("version", "")),
            target=str(tool_value.get("target", "")),
        )
    return OrbisToolInvocation(
        profile=str(value.get("profile", "unknown")),
        command=tuple(str(item) for item in cast(list[object], value.get("command", []))),
        flags=tuple(str(item) for item in cast(list[object], value.get("flags", []))),
        return_status=_optional_int(value.get("return_status")),
        status=str(value.get("status", "unknown")),
        stdout_path=_optional_string(value.get("stdout_path")),
        stderr_path=_optional_string(value.get("stderr_path")),
        stdout_sha256=_optional_string(value.get("stdout_sha256")),
        stderr_sha256=_optional_string(value.get("stderr_sha256")),
        tool_identity=tool,
        duration_ms=_optional_float(value.get("duration_ms")),
        diagnostics=tuple(str(item) for item in cast(list[object], value.get("diagnostics", []))),
        cache_key=_optional_string(value.get("cache_key")),
        requested_triple=_optional_string(value.get("requested_triple")),
        effective_triple=_optional_string(value.get("effective_triple")),
        target_status=_optional_string(value.get("target_status")),
        range_start=_optional_int(value.get("range_start")),
        range_end=_optional_int(value.get("range_end")),
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else _required_int(value)


def _required_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Expected integer evidence, got {type(value).__name__}")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"Expected float evidence, got {type(value).__name__}")

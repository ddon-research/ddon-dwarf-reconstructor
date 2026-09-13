"""Typer command owned by the optional implementation-validation feature."""

from __future__ import annotations

from ..artifact_cli_support import run_operation as _run_operation
from ..artifact_cli_support import write_result as _write_result
from .cli import execute_implementation_validation
from .options import (
    AbiProbeManifestOption,
    AssemblyProfileOption,
    DwarfStoreOption,
    ElfArgument,
    LoadBaseOption,
    NidDatabaseOption,
    NidDatabaseProvenanceOption,
    OrbisAsOption,
    OrbisClangOption,
    OrbisLdOption,
    OrbisObjdumpOption,
    OrbisReadelfOption,
    OriginalAddressesOption,
    OutputOption,
    ReportOption,
    SdkRootOption,
    ToolEvidenceOption,
    ToolTimeoutSecondsOption,
)


def validate_implementation_command(
    elf: ElfArgument,
    implementation_report: ReportOption,
    output_dir: OutputOption,
    load_base: LoadBaseOption = None,
    original_addresses: OriginalAddressesOption = False,
    dwarf_store: DwarfStoreOption = None,
    nid_database: NidDatabaseOption = None,
    nid_database_provenance: NidDatabaseProvenanceOption = None,
    sdk_root: SdkRootOption = None,
    orbis_as: OrbisAsOption = None,
    orbis_clang: OrbisClangOption = None,
    orbis_readelf: OrbisReadelfOption = None,
    orbis_objdump: OrbisObjdumpOption = None,
    orbis_ld: OrbisLdOption = None,
    tool_evidence: ToolEvidenceOption = None,
    abi_probe_manifest: AbiProbeManifestOption = None,
    tool_timeout_seconds: ToolTimeoutSecondsOption = None,
    assembly_profile: AssemblyProfileOption = "byte-replay",
) -> None:
    """Validate relocation, NID, ABI, safety, compiler, and parity evidence."""

    _run_operation(
        lambda: execute_implementation_validation(
            elf,
            implementation_report,
            output_dir,
            load_base=load_base,
            original_addresses=original_addresses,
            dwarf_store=dwarf_store,
            nid_database=nid_database,
            nid_database_provenance=nid_database_provenance,
            sdk_root=sdk_root,
            orbis_as=orbis_as,
            orbis_clang=orbis_clang,
            orbis_readelf=orbis_readelf,
            orbis_objdump=orbis_objdump,
            orbis_ld=orbis_ld,
            tool_evidence=tuple(tool_evidence or ()),
            abi_probe_manifest=abi_probe_manifest,
            tool_timeout_seconds=tool_timeout_seconds,
            assembly_profile=assembly_profile,
            write_result=_write_result,
        )
    )


__all__ = ["validate_implementation_command"]

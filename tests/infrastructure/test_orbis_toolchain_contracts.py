"""Tests for the reviewed local Orbis toolchain contracts and identity boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    NidBinding,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.domain.models.orbis_toolchain import OrbisToolchainContract
from ddon_dwarf_reconstructor.domain.models.sysmodule import SysmoduleId
from ddon_dwarf_reconstructor.infrastructure.orbis_toolchain_contracts import (
    SDK8_PROFILE_ID,
    SDK12_CONTRACT,
    SDK12_PROFILE_ID,
    get_toolchain_contract,
    profile_id_for_path,
    select_toolchain_profile,
)
from ddon_dwarf_reconstructor.infrastructure.sysmodule_catalog import (
    SYSMODULE_IDS,
    get_sysmodule_id,
    is_sysmodule_value,
    list_sysmodule_ids,
)


@pytest.mark.unit
@pytest.mark.functional
def test_sdk12_is_the_promoted_contract_and_sdk8_is_explicit_history() -> None:
    assert get_toolchain_contract(SDK12_PROFILE_ID) is SDK12_CONTRACT
    assert SDK12_CONTRACT.sdk_version == "12.000"
    assert SDK12_CONTRACT.target_triple == "x86_64-scei-ps4"
    assert SDK12_CONTRACT.integrated_assembler_default is True
    assert "EF_FFUNC_DATA_SECS_ENABLED=0x04000000" in SDK12_CONTRACT.elf_flags
    assert "R_X86_64_ORBIS_GOTPCREL_LOAD=0x28" in SDK12_CONTRACT.relocation_definitions
    assert "varargs-m256=stack" in SDK12_CONTRACT.abi_rules
    assert "register-classes=integer,sse,x87,memory" in SDK12_CONTRACT.abi_rules
    assert "enum-char=underlying-type-and-width" in SDK12_CONTRACT.abi_rules
    assert "tls=fs-segment-relative" in SDK12_CONTRACT.abi_rules
    assert "int128=single-register-shortage-spills-whole-argument" in SDK12_CONTRACT.abi_rules
    assert "sysmodule-ids=not-nid-module-identities" in SDK12_CONTRACT.abi_rules
    assert all(Path(item).drive == "D:" for item in SDK12_CONTRACT.documentation_sources)

    selected, diagnostics = select_toolchain_profile(None)
    assert selected == SDK12_PROFILE_ID
    assert diagnostics
    assert profile_id_for_path(Path(r"D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-as.exe")) == (
        SDK8_PROFILE_ID
    )
    selected, diagnostics = select_toolchain_profile(
        Path(r"D:\SCE\ORBIS SDKs\8.000"),
        (Path(r"D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-as.exe"),),
    )
    assert selected == SDK8_PROFILE_ID
    assert diagnostics == ()


@pytest.mark.unit
@pytest.mark.functional
def test_mixed_sdk_tool_families_fail_closed() -> None:
    with pytest.raises(ValueError, match="Mixed Orbis SDK"):
        select_toolchain_profile(
            Path(r"D:\SCE\ORBIS SDKs\12.000"),
            (Path(r"D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-as.exe"),),
        )


@pytest.mark.unit
@pytest.mark.functional
def test_sysmodule_catalog_is_typed_and_not_a_nid_binding() -> None:
    fiber = get_sysmodule_id("SCE_SYSMODULE_FIBER")
    assert isinstance(fiber, SysmoduleId)
    assert fiber.value == 6
    assert fiber.source.endswith("ps4-module-ids.html")
    assert len(SYSMODULE_IDS) == 91
    assert list_sysmodule_ids()[0] is fiber
    assert is_sysmodule_value(6) is True

    binding = NidBinding(
        relocation_id="reloc",
        encoded_symbol="lib#name#nid",
        encoded_nid="nid",
        module_id=6,
        library_id=7,
        version_major=None,
        version_minor=None,
        resolved_name=None,
        source=None,
        status=ValidationStatus.NOT_OBSERVED,
    )
    assert binding.identity_kind == "sce_dynamic_tag"
    assert binding.to_dict()["identity_kind"] == "sce_dynamic_tag"
    assert not isinstance(binding, SysmoduleId)


@pytest.mark.unit
@pytest.mark.functional
def test_contract_serialization_keeps_schema_and_provenance() -> None:
    payload = SDK12_CONTRACT.to_dict()
    assert payload["schema_version"] == "1.0"
    assert payload["profile_id"] == SDK12_PROFILE_ID
    assert payload["documentation_sources"]
    assert OrbisToolchainContract(**payload) == SDK12_CONTRACT

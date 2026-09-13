"""Flat symbol publication and IDA-style assembly evidence tests."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.application.generators.generation_contracts import (
    SymbolExtractionResult,
)
from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction, OrbisReference
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    CodeRange,
    ImplementationDiscoveryReport,
    ImplementationRelation,
    ImplementationStatus,
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
)
from ddon_dwarf_reconstructor.infrastructure import symbol_output
from ddon_dwarf_reconstructor.infrastructure.elf_platform import ELFPlatform
from ddon_dwarf_reconstructor.infrastructure.symbol_output import (
    SymbolPublisher,
    infer_client_version,
    render_ida_assembly,
)
from ddon_dwarf_reconstructor.infrastructure.symbol_output_methods import (
    method_class_key,
    method_owner,
)


def _class(name: str, die_offset: int) -> ClassInfo:
    return ClassInfo(
        name=name,
        byte_size=8,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        declaration_file=f"{name}.h",
        die_offset=die_offset,
        cu_offset=die_offset + 100,
        qualified_name=name,
    )


def _symbols() -> SymbolExtractionResult:
    headers = {
        "RootA/RootA.h": "class RootA {};\n",
        "shared/MtDataReader.h": "class MtDataReader {};\n",
    }
    return SymbolExtractionResult(
        requested_symbols=("RootA", "RootB"),
        headers=headers,
        header_owners={"RootA/RootA.h": "RootA", "shared/MtDataReader.h": "shared"},
        header_classes={
            "RootA/RootA.h": ("RootA",),
            "shared/MtDataReader.h": ("MtDataReader",),
        },
        class_owners={"RootA": "RootA", "MtDataReader": "shared"},
        class_origins={"RootA": ("RootA",), "MtDataReader": ("RootA", "RootB")},
        class_identities={"RootA": "RootA|101|1", "MtDataReader": "MtDataReader|103|3"},
        class_infos={"RootA": _class("RootA", 1), "MtDataReader": _class("MtDataReader", 3)},
        root_statuses={"RootA": "success", "RootB": "success"},
        configuration={"include_method_signatures": True},
    )


def _report(symbols: SymbolExtractionResult) -> ImplementationDiscoveryReport:
    method = MethodAssemblyEvidence(
        owner="RootA",
        method_name="load",
        signature="void load(MtDataReader&)",
        definition_signature="void RootA::load(MtDataReader&)",
        declaration_die_offset=10,
        declaration_cu_offset=20,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        candidates=(
            MethodImplementationCandidate(
                declaration_die_offset=10,
                implementation_die_offset=11,
                declaration_cu_offset=20,
                implementation_cu_offset=21,
                relation=ImplementationRelation.DIRECT,
                name="load",
                linkage_name="RootA::load(MtDataReader&)",
                code_ranges=(CodeRange(0x1000, 0x1005, "DWARF low_pc"),),
            ),
        ),
        selected_implementation_die_offset=11,
        selected_function_name="RootA::load(MtDataReader&)",
        selected_function_address=0x1000,
        selected_function_size=5,
        instructions=(
            OrbisInstruction(
                address=0x1000,
                raw_bytes="e8 00 00 00 00",
                mnemonic="callq",
                operands="0x2000 <MtDataReader::read()>",
                source_file=r"D:\headers\MtDataReader.h",
                source_line=46,
                call_target_address=0x2000,
                call_target_name="MtDataReader::read()",
                references=(
                    OrbisReference(
                        kind="direct_call",
                        address=0x2000,
                        resolved_name="MtDataReader::read()",
                        raw_operand="0x2000 <MtDataReader::read()>",
                        resolution_status="resolved",
                    ),
                ),
                raw_line="0000000000001000 <RootA::load(MtDataReader&)>: callq 0x2000 <MtDataReader::read()>",
            ),
        ),
    )
    return ImplementationDiscoveryReport(
        root_symbol="symbols",
        header_bundle_sha256=symbols.header_bundle.sha256,
        status=ImplementationStatus.MATCHED,
        methods=(method,),
        elf_sha256="elf-sha",
    )


@pytest.mark.unit
@pytest.mark.functional
def test_version_inference_uses_path_token_and_unknown_fallback() -> None:
    assert infer_client_version(Path(r"D:\research\PS4_02020005\DDOORBIS.elf")).value == (
        "02020005"
    )
    assert infer_client_version(Path(r"D:\research\PS4_02020005\DDOORBIS.elf")).source == (
        "parent-path"
    )
    unknown = infer_client_version(Path("resources/DDOORBIS.elf"))
    assert unknown.value == "unknown"
    assert unknown.diagnostics
    ambiguous = infer_client_version(Path(r"D:\research\02020005\03030006\DDOORBIS.elf"))
    assert ambiguous.value == "unknown"
    assert "ambiguous" in ambiguous.diagnostics[0]


@pytest.mark.unit
@pytest.mark.functional
def test_symbol_publisher_writes_flat_versioned_asm_with_comment_source_rows(
    tmp_path: Path,
) -> None:
    symbols = _symbols()
    target = SymbolPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        Path(r"D:\research\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf"),
        "elf-sha",
        symbols,
        _report(symbols),
        emit_assembly=True,
        emit_sources=True,
    )

    assert target == tmp_path / "ps4-02020005"
    asm_files = tuple(target.rglob("*.asm"))
    assert len(asm_files) == 1
    assert "methods" not in asm_files[0].parts
    content = asm_files[0].read_text(encoding="utf-8")
    assert "; signature: void load(MtDataReader&)" in content
    assert "; definition_signature: void RootA::load(MtDataReader&)" in content
    assert "; pseudo_symbol:" in content
    assert "; pseudo_call: MtDataReader::read()" in content
    assert "; source: D:\\headers\\MtDataReader.h:46" in content
    assert "; file_offset: unknown" in content
    assert "; source_location: D:\\headers\\MtDataReader.h:46" in content
    assert "\nD:\\headers\\MtDataReader.h:46\n" not in content
    manifest = json.loads((target / "symbols.manifest.json").read_text(encoding="utf-8"))
    assert manifest["client_version"] == "02020005"
    assert manifest["input_list_sha256"]
    assert manifest["roots"]["RootA"]["status"] == "success"
    assert manifest["file_hashes"]["implementation-report.json"]["sha256"]
    assert manifest["implementation"]["assembly_file_count"] == 1
    assert manifest["implementation"]["source_file_count"] == 1
    assert (target / "shared" / "MtDataReader.h").exists()
    assert len(tuple(target.rglob("*.s"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_source_location_rows_are_never_emitted_as_assembler_lines() -> None:
    method = MethodAssemblyEvidence(
        owner="RootA",
        method_name="load",
        signature="void load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        instructions=(
            OrbisInstruction(
                address=0x1000,
                raw_bytes="90",
                mnemonic="nop",
                operands="",
                raw_line=r"D:\headers\RootA.cpp:46",
            ),
        ),
    )

    content = render_ida_assembly(method, "RootA-load-hash")

    assert f"\n{method.instructions[0].raw_line}\n" not in content
    assert "0000000000001000: 90 nop" in content


@pytest.mark.unit
@pytest.mark.regression
def test_method_ownership_fails_closed_for_ambiguous_display_name() -> None:
    symbols = replace(
        _symbols(),
        class_infos={
            "duplicate-a": _class("Duplicate", 1),
            "duplicate-b": _class("Duplicate", 2),
        },
        class_owners={"duplicate-a": "RootA", "duplicate-b": "RootB"},
        class_origins={"duplicate-a": ("RootA",), "duplicate-b": ("RootB",)},
    )
    report = _report(symbols)
    method = replace(report.methods[0], owner="Duplicate", owner_class_key=None)

    assert method_class_key(symbols, method) is None
    assert method_owner(symbols, method) == "shared"


@pytest.mark.unit
@pytest.mark.functional
def test_symbol_publisher_can_omit_all_context_json(tmp_path: Path) -> None:
    symbols = _symbols()
    target = SymbolPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        Path("resources/DDOORBIS.elf"),
        "elf-sha",
        symbols,
        _report(symbols),
        emit_assembly=True,
        emit_sources=True,
        generate_context=False,
    )

    assert target == tmp_path / "ps4-unknown"
    assert tuple(target.rglob("*.json")) == ()
    assert tuple(target.rglob("*.h"))
    assert tuple(target.rglob("*.asm"))
    assert len(tuple(target.rglob("*.s"))) == 1
    assert tuple(target.rglob("*.o")) == ()


@pytest.mark.unit
@pytest.mark.regression
def test_symbol_publisher_rolls_back_staging_and_preserves_previous_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "ps4-unknown"
    target.mkdir(parents=True)
    (target / "previous.txt").write_text("previous\n", encoding="utf-8")

    def fail_commit(_stage: Path, _target: Path) -> None:
        raise OSError("simulated symbol publication failure")

    monkeypatch.setattr(symbol_output, "_commit_directory", fail_commit)

    with pytest.raises(OSError, match="simulated"):
        SymbolPublisher().publish(
            tmp_path,
            ELFPlatform.PS4,
            Path("resources/DDOORBIS.elf"),
            "elf-sha",
            _symbols(),
        )

    assert (target / "previous.txt").read_text(encoding="utf-8") == "previous\n"
    assert not tuple(tmp_path.glob(".ps4-unknown.staging-*"))


@pytest.mark.unit
@pytest.mark.regression
@pytest.mark.parametrize("relative", ["../escape.h", ".", "/root.h", "C:escape.h", "\\root.h"])
def test_symbol_publisher_rejects_uncontained_header_paths(
    tmp_path: Path, relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name != "nt" and relative in {"C:escape.h", "\\root.h"}:
        pytest.skip("Windows path syntax")
    symbols = replace(_symbols(), headers={relative: "class Escape {};\n"})
    # Do not let a regressed validator write outside this test's owned directory.
    write = symbol_output._write_text

    def contained_write(path: Path, content: str) -> None:
        assert path.resolve().is_relative_to(tmp_path.resolve()), "escaped test publication"
        write(path, content)

    monkeypatch.setattr(symbol_output, "_write_text", contained_write)
    with pytest.raises(ValueError, match="relative and contained"):
        SymbolPublisher().publish(
            tmp_path, ELFPlatform.PS4, Path("DDOORBIS.elf"), "elf-sha", symbols
        )
    assert not list(tmp_path.iterdir())

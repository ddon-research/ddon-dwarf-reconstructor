"""Tests for deterministic DWARF knowledge graph exports."""

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.application.exporters import KnowledgeExporter
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisToolIdentity,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.unit
def test_dwarf_method_ids_are_scoped_to_the_selected_owner_die(tmp_path: Path) -> None:
    """Duplicate class definitions must remain distinct source observations."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    exporter = KnowledgeExporter(elf_path, "ps4-02020005")
    method = MethodInfo("load", "bool", parameters=[ParameterInfo("in", "MtStream&")])
    first = ClassInfo("rLayout", 528, [], [method], [], [], [], [], die_offset=0x76133)
    second = ClassInfo("rLayout", 528, [], [method], [], [], [], [], die_offset=0x117EC452)

    first_identity = exporter._method_identity(first, method)
    second_identity = exporter._method_identity(second, method)

    assert first_identity[:2] == second_identity[:2]
    assert first_identity[2] != second_identity[2]
    assert ":dwarf:76133:" in first_identity[2]
    assert ":dwarf:117ec452:" in second_identity[2]


@pytest.mark.unit
def test_export_projects_reconstructed_cpp_and_orbis_instructions(tmp_path: Path) -> None:
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        "rLayout",
        528,
        [],
        [MethodInfo("load", "bool", parameters=[ParameterInfo("in", "MtStream&")])],
        [],
        [],
        [],
        [],
        declaration_file="rLayout.h",
        declaration_line=40,
        die_offset=0x117EC452,
    )
    report = OrbisDisassemblyReport(
        artifact_key="a" * 64,
        build_root="rLayout",
        elf_sha256="b" * 64,
        tool=OrbisToolIdentity("c" * 64, "Orbis 8.00", "elf64-x86-64-freebsd"),
        flags=("-EL", "-l", "-C", "-w", "-d"),
        parser_version="fixture-v1",
        functions=(
            OrbisFunctionDisassembly(
                OrbisFunctionSymbol(0x693E60, 0xC85, ".text", "rLayout::load(MtStream&)"),
                (
                    OrbisInstruction(
                        0x693E60,
                        "e86af7ffff",
                        "callq",
                        "6935d0 <rLayout::destruct()>",
                        "rLayout.cpp",
                        178,
                        0x6935D0,
                        "rLayout::destruct()",
                    ),
                ),
            ),
        ),
    )

    manifest_path = KnowledgeExporter(elf_path, "ps4-02020005").export(
        "rLayout",
        {"rLayout": layout},
        ["rLayout"],
        tmp_path / "fused-export",
        reconstructed_cpp="struct rLayout {};\n",
        disassembly_report=report,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = _read_jsonl(manifest_path.parent / "nodes.jsonl")
    relationships = _read_jsonl(manifest_path.parent / "relationships.jsonl")
    instructions = _read_jsonl(manifest_path.parent / "instructions.jsonl")

    assert manifest["disassembly"]["artifact_key"] == "a" * 64
    assert manifest["files"]["instructions"]["sha256"]
    assert manifest["files"]["reconstructed_cpp"]["sha256"]
    assert any(node["kind"] == "ReconstructedCppUnit" for node in nodes)
    assert any(
        node["kind"] == "DisassemblyUnit" and node["properties"]["instruction_count"] == 1
        for node in nodes
    )
    assert any(relationship["type"] == "CALLS" for relationship in relationships)
    assert instructions[0]["address"] == 0x693E60

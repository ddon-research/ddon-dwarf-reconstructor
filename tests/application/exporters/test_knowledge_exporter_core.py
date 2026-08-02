"""Tests for deterministic DWARF knowledge graph exports."""

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.application.exporters import KnowledgeExporter
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog


def _exporter(elf_path: Path, **kwargs: object) -> KnowledgeExporter:
    return KnowledgeExporter(
        elf_path,
        "ps4-02020005",
        source_hash=SourceIdentityCatalog().sha256,
        **kwargs,
    )


@pytest.mark.unit
def test_export_preserves_layout_and_source_metadata(tmp_path: Path) -> None:
    """Exported field records retain offsets, source IDs, and inheritance links."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    base = ClassInfo(
        name="cResource",
        byte_size=16,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=10,
        cu_offset=1,
    )
    layout = ClassInfo(
        name="rLayout",
        byte_size=496,
        members=[MemberInfo("mSetInfo", "rLayout::SetInfo", type_offset=30, offset=112)],
        methods=[MethodInfo("load", "bool")],
        base_classes=["cResource"],
        enums=[],
        nested_structs=[],
        unions=[],
        declaration_file="rLayout.h",
        declaration_line=42,
        die_offset=20,
        cu_offset=2,
    )
    nested = ClassInfo(
        name="rLayout::SetInfo",
        byte_size=20,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=30,
        cu_offset=2,
    )

    manifest_path = _exporter(elf_path).export(
        "rLayout",
        {"cResource": base, "rLayout": layout, "rLayout::SetInfo": nested},
        ["cResource", "rLayout", "rLayout::SetInfo"],
        tmp_path / "export",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relationships = [
        json.loads(line)
        for line in (manifest_path.parent / "relationships.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    nodes = [
        json.loads(line)
        for line in (manifest_path.parent / "nodes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["build_id"] == "ps4-02020005"
    assert manifest["root_symbol"] == "rLayout"
    assert any(
        node["kind"] == "Field"
        and node["properties"]["name"] == "mSetInfo"
        and node["properties"]["offset"] == 112
        for node in nodes
    )
    assert any(relationship["type"] == "HAS_FIELD" for relationship in relationships)
    assert any(relationship["type"] == "INHERITS" for relationship in relationships)


@pytest.mark.unit
def test_export_records_root_authority_in_manifest(tmp_path: Path) -> None:
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo("rLayout", 528, [], [], [], [], [], [], die_offset=0x117EC452)
    authority = {"symbol": "rLayout", "die_offset_hex": "0x117ec452"}

    manifest_path = _exporter(elf_path).export(
        "rLayout",
        {"rLayout": layout},
        ["rLayout"],
        tmp_path / "authority-export",
        root_authority=authority,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["root_authority"] == authority


@pytest.mark.unit
def test_export_hashes_large_elf_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The strong source digest is reused across fresh exporter instances."""
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "artifact-cache"))
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="rLayout",
        byte_size=496,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=20,
        cu_offset=2,
    )
    from ddon_dwarf_reconstructor.infrastructure import artifacts

    original_hash = artifacts.sha256_file
    hashed_paths: list[Path] = []
    source_hash = artifacts.SourceIdentityCatalog().sha256

    def counting_hash(path: Path) -> str:
        hashed_paths.append(path)
        return original_hash(path)

    monkeypatch.setattr(artifacts, "sha256_file", counting_hash)
    KnowledgeExporter(elf_path, "ps4-02020005", source_hash=source_hash).export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "first"
    )
    KnowledgeExporter(elf_path, "ps4-02020005", source_hash=source_hash).export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "second"
    )

    assert hashed_paths == [elf_path.resolve()]


@pytest.mark.unit
def test_export_retains_logical_field_reference_outside_concrete_closure(tmp_path: Path) -> None:
    """A partial closure must retain the exact reference and a diagnostic."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="rLayout",
        byte_size=496,
        members=[MemberInfo("mSetInfo", "rLayout::SetInfo", type_offset=30, offset=112)],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=20,
        cu_offset=2,
    )

    manifest_path = _exporter(elf_path).export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "export"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = [
        json.loads(line)
        for line in (manifest_path.parent / "nodes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    relationships = [
        json.loads(line)
        for line in (manifest_path.parent / "relationships.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert manifest["completeness"] == "partial"
    assert "field rLayout::mSetInfo references unresolved type" in manifest["diagnostics"][0]
    assert any(node["id"] == "logical-type:rLayout::SetInfo" for node in nodes)
    assert any(
        relationship["type"] == "REFERENCES_TYPE"
        and relationship["target_id"] == "logical-type:rLayout::SetInfo"
        and relationship["properties"]["resolution"] == "logical_only"
        for relationship in relationships
    )


@pytest.mark.unit
def test_export_keeps_signature_only_references_outside_layout_closure(tmp_path: Path) -> None:
    """Method types remain signature facts without forcing complete layouts."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="rLayout",
        byte_size=496,
        members=[],
        methods=[
            MethodInfo(
                "load",
                "rLayout::Result",
                return_type_offset=41,
                parameters=[ParameterInfo("entry", "rLayout::SetInfo", type_offset=30)],
            )
        ],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=20,
        cu_offset=2,
    )

    manifest_path = _exporter(elf_path).export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "export"
    )

    assert manifest_path.exists()


@pytest.mark.unit
def test_export_accepts_self_and_builtin_references_via_offsets(tmp_path: Path) -> None:
    """Qualified self-references and builtin aliases should not fail closure validation."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="stLayoutID",
        byte_size=8,
        members=[
            MemberInfo("mValue", "u32", type_offset=16686, offset=0),
            MemberInfo("mReserved", "void[4]", type_offset=16687, offset=4),
        ],
        methods=[
            MethodInfo(
                "operator==",
                "bool",
                return_type_offset=8079,
                parameters=[ParameterInfo("param1", "const stLayoutID&", type_offset=477216)],
            )
        ],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=477216,
        cu_offset=2,
    )

    manifest_path = _exporter(elf_path).export(
        "stLayoutID",
        {"stLayoutID": layout},
        ["stLayoutID"],
        tmp_path / "export",
    )

    assert manifest_path.exists()


@pytest.mark.unit
def test_export_ignores_non_structural_unresolved_offsets(tmp_path: Path) -> None:
    """Unresolved typedef/enum/array-like offsets should not fail structural export."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="MtAllocator",
        byte_size=32,
        members=[MemberInfo("mName", "MT_CTSTR", type_offset=35167, offset=0)],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=200,
        cu_offset=2,
    )

    manifest_path = _exporter(
        elf_path,
        requires_resolution=lambda offset: offset != 35167,
    ).export(
        "MtAllocator",
        {"MtAllocator": layout},
        ["MtAllocator"],
        tmp_path / "export",
    )

    assert manifest_path.exists()


@pytest.mark.unit
def test_export_gives_overloaded_methods_distinct_stable_ids(tmp_path: Path) -> None:
    """Function identity includes ordered parameter types, not only the method name."""
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"deterministic dwarf fixture")
    layout = ClassInfo(
        name="rLayout",
        byte_size=496,
        members=[],
        methods=[
            MethodInfo(
                "load",
                "bool",
                parameters=[ParameterInfo("path", "const char*")],
            ),
            MethodInfo(
                "load",
                "bool",
                parameters=[ParameterInfo("stream", "MtStream&")],
            ),
        ],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        die_offset=20,
        cu_offset=2,
    )
    exporter = _exporter(elf_path)

    first_manifest = exporter.export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "first"
    )
    second_manifest = exporter.export(
        "rLayout", {"rLayout": layout}, ["rLayout"], tmp_path / "second"
    )
    first_nodes = [
        json.loads(line)
        for line in (first_manifest.parent / "nodes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    functions = [node for node in first_nodes if node["kind"] == "Function"]

    assert len(functions) == 2
    assert len({function["id"] for function in functions}) == 2
    assert {function["properties"]["signature"] for function in functions} == {
        "bool rLayout::load(const char*)",
        "bool rLayout::load(MtStream&)",
    }
    assert (first_manifest.parent / "nodes.jsonl").read_bytes() == (
        second_manifest.parent / "nodes.jsonl"
    ).read_bytes()

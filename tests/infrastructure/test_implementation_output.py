"""Tests for additive implementation-report publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction, OrbisReference
from ddon_dwarf_reconstructor.domain.models.disassembly_scope import DisassemblyTarget
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ArtifactDescriptor,
    CodeRange,
    ImplementationArtifactProfile,
    ImplementationDiscoveryReport,
    ImplementationRelation,
    ImplementationStatus,
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
    SourceArtifactMetadata,
)
from ddon_dwarf_reconstructor.infrastructure.elf_platform import ELFPlatform
from ddon_dwarf_reconstructor.infrastructure.implementation_output import (
    AtomicImplementationReportPublisher,
)


class _BadArtifactRenderer:
    profile = ImplementationArtifactProfile.CANONICAL_ASSEMBLY

    def render(
        self,
        _method: MethodAssemblyEvidence,
        includes: tuple[str, ...],
        method_id: str,
        _report_filename: str,
    ) -> tuple[SourceArtifactMetadata, dict[Path, str]]:
        relative_path = Path("methods") / method_id / f"{method_id}.cpp"
        artifact = SourceArtifactMetadata(
            method_id=method_id,
            generation_status="generated",
            header_includes=includes,
            artifacts=(
                ArtifactDescriptor(kind="cpp", path=relative_path.as_posix(), sha256="0" * 64),
            ),
        )
        return artifact, {relative_path: "bad"}


_HEADER_BUNDLE_SHA256 = "481f29bfcf936f0353d73dba53137ef39df4db7a6ce21e6981d83caeec131d40"


@pytest.mark.unit
@pytest.mark.functional
def test_publisher_writes_a_separate_source_bound_report(tmp_path: Path) -> None:
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256="header-sha",
        status=ImplementationStatus.NOT_OBSERVED,
        methods=(),
        elf_sha256="elf-sha",
    )

    path = AtomicImplementationReportPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout::load",
        report,
    )

    assert path == tmp_path / "ps4" / "implementations" / "0001-rLayout_load.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["header_bundle_sha256"] == "header-sha"
    assert payload["elf_sha256"] == "elf-sha"
    assert list(path.parent.glob("*.tmp")) == []


@pytest.mark.unit
@pytest.mark.functional
def test_report_binds_the_published_header_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ps4" / "header-bundle.manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text('{"files": {}}\n', encoding="utf-8")
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256="header-sha",
        status=ImplementationStatus.NOT_OBSERVED,
        methods=(),
        elf_sha256="elf-sha",
    )

    path = AtomicImplementationReportPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        report,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert (
        payload["header_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )


@pytest.mark.unit
@pytest.mark.functional
def test_report_persists_the_dwarf_target_manifest_and_scope_identity() -> None:
    target = DisassemblyTarget(
        target_id="cu:1:die:2",
        declaration_die_offset=2,
        implementation_die_offset=3,
        declaration_cu_offset=1,
        implementation_cu_offset=1,
        ranges=((0x1000, 0x1010),),
        qualified_name="Thing::load",
        linkage_name="_ZN5Thing4loadEv",
        signature="void Thing::load()",
    )
    report = ImplementationDiscoveryReport(
        root_symbol="Thing",
        header_bundle_sha256="header-sha",
        status=ImplementationStatus.NOT_OBSERVED,
        methods=(),
        disassembly_scope_hash="scope-sha",
        disassembly_target_manifest=(target,),
    )

    payload = report.to_dict()

    assert payload["schema_version"] == "4.2"
    assert payload["disassembly_scope_hash"] == "scope-sha"
    assert payload["disassembly_target_manifest"] == [target.to_dict()]


def _source_report() -> ImplementationDiscoveryReport:
    matched = MethodAssemblyEvidence(
        owner="rLayout",
        method_name="load",
        signature="load()",
        definition_signature="void rLayout::load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        candidates=(
            MethodImplementationCandidate(
                declaration_die_offset=1,
                implementation_die_offset=4,
                declaration_cu_offset=2,
                implementation_cu_offset=3,
                relation=ImplementationRelation.DIRECT,
                name="load",
                linkage_name=None,
                code_ranges=(CodeRange(0x1000, 0x1001, "test"),),
            ),
        ),
        selected_implementation_die_offset=4,
        selected_function_name="rLayout::load()",
        selected_function_address=0x1000,
        selected_function_size=1,
        instructions=(
            OrbisInstruction(
                0x1000,
                "90",
                "mov",
                "%rbp,%rax",
                source_file="rLayout.cpp",
                source_line=10,
                references=(
                    OrbisReference(
                        kind="data",
                        resolved_name="rLayout::DTI",
                        raw_operand="%rbp,%rax",
                        resolution_status="resolved",
                    ),
                ),
                raw_line="raw tool line",
            ),
        ),
        raw_disassembly="raw tool line\n",
    )
    ambiguous = MethodAssemblyEvidence(
        owner="rLayout",
        method_name="other",
        signature="other()",
        declaration_die_offset=3,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.AMBIGUOUS,
        assembly_status=ImplementationStatus.AMBIGUOUS,
    )
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256=_HEADER_BUNDLE_SHA256,
        status=ImplementationStatus.PARTIAL,
        methods=(matched, ambiguous),
        header_files=("rLayout.h",),
    )
    return report


def _publish_source_bundle(tmp_path: Path) -> tuple[Path, Path]:
    report = _source_report()
    path = AtomicImplementationReportPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        report,
        emit_sources=True,
        headers={"rLayout.h": "header"},
    )
    return path, path.with_suffix("")


def _bundle_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "source-bundle.manifest.json":
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_bundle_manifest(path: Path, bundle: Path) -> None:
    manifest_path = bundle / "source-bundle.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {
        "artifact_profile",
        "bundle_sha256",
        "elf_sha256",
        "file_count",
        "header_bundle_sha256",
        "header_manifest_sha256",
        "publication_status",
        "report_path",
        "report_sha256",
        "root_symbol",
        "schema_version",
    }
    assert "files" not in manifest
    assert "methods" not in manifest
    report_bytes = path.read_bytes()
    assert manifest["report_sha256"] == hashlib.sha256(report_bytes).hexdigest()
    assert manifest["bundle_sha256"] == _bundle_digest(bundle)
    assert manifest["schema_version"] == "3.1"
    assert manifest["file_count"] == 3
    assert (manifest_path.parent / manifest["report_path"]).resolve() == path.resolve()
    assert list(path.parent.glob("*.tmp")) == []


@pytest.mark.unit
@pytest.mark.functional
def test_publisher_emits_only_unique_matched_method_assembly(tmp_path: Path) -> None:
    path, bundle = _publish_source_bundle(tmp_path)

    assembly_files = tuple(bundle.rglob("*.s"))
    assert len(assembly_files) == 1
    assert ".text" in assembly_files[0].read_text(encoding="utf-8")
    assert ".byte 0x90" in assembly_files[0].read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source_status"] == "generated"
    assert payload["schema_version"] == "4.2"
    assert payload["artifact_profile"] == "canonical-assembly"
    assert [item["kind"] for item in payload["methods"][0]["source_artifact"]["artifacts"]] == [
        "raw-assembly",
        "canonical-assembly",
        "context",
    ]
    assert payload["methods"][1]["source_artifact"]["generation_status"] == "not_eligible"
    assert "source_artifacts" not in payload
    assert "references" not in payload["methods"][0]
    assert "raw_line" not in payload["methods"][0]["instructions"][0]
    assert payload["methods"][0]["raw_disassembly"] == "raw tool line\n"
    assert payload["methods"][0]["instructions"][0]["references"][0]["resolved_name"] == (
        "rLayout::DTI"
    )
    assert {item["code"] for item in payload["limitations"]} == {
        "abi_not_inferred",
        "semantic_equivalence_not_validated",
        "external_declaration_not_synthesized",
        "relocation_application_not_validated",
        "register_stack_safety_not_validated",
        "orbis_compiler_not_validated",
        "live_behavior_not_observed",
    }
    assert not tuple(bundle.rglob("*.cpp"))
    raw_files = tuple(bundle.rglob("*.raw.asm"))
    context_files = tuple(bundle.rglob("*.context.json"))
    assert len(raw_files) == len(context_files) == 1
    assert raw_files[0].read_text(encoding="utf-8") == "raw tool line\n"
    raw_descriptor = next(
        item
        for item in payload["methods"][0]["source_artifact"]["artifacts"]
        if item["kind"] == "raw-assembly"
    )
    assert raw_descriptor["sha256"] == hashlib.sha256(raw_files[0].read_bytes()).hexdigest()
    assert raw_descriptor["byte_length"] == raw_files[0].stat().st_size
    context = json.loads(context_files[0].read_text(encoding="utf-8"))
    assert context["schema_version"] == "implementation-context/1.0"
    assert context["source_binding"]["header_bundle_sha256"] == _HEADER_BUNDLE_SHA256
    assert context["evidence_status"]["live_behavior"] == "not_observed"
    assert context["artifacts"][0]["kind"] == "raw-assembly"
    assert not tuple(bundle.rglob("*.disassembly.txt"))
    assert not tuple(bundle.rglob("*.references.json"))
    assert not tuple(bundle.rglob("reconstruction-notes.txt"))
    _assert_bundle_manifest(path, bundle)


@pytest.mark.unit
@pytest.mark.functional
def test_publisher_adds_sdk_object_bytes_when_assembler_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ddon_dwarf_reconstructor.infrastructure.implementation_artifacts.assemble_canonical_source",
        lambda _method_id, _source, _assembler: (b"accepted-object", ()),
    )

    report_path = AtomicImplementationReportPublisher(assembler=Path("orbis-as")).publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        _source_report(),
        emit_sources=True,
        headers={"rLayout.h": "header"},
    )

    bundle = report_path.with_suffix("")
    object_files = tuple(bundle.rglob("*.o"))
    assert len(object_files) == 1
    assert object_files[0].read_bytes() == b"accepted-object"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert [item["kind"] for item in payload["methods"][0]["source_artifact"]["artifacts"]] == [
        "raw-assembly",
        "canonical-assembly",
        "object",
        "context",
    ]
    assert (
        json.loads((bundle / "source-bundle.manifest.json").read_text(encoding="utf-8"))[
            "file_count"
        ]
        == 4
    )


@pytest.mark.unit
@pytest.mark.functional
def test_unmapped_matched_method_is_retained_without_cpp(tmp_path: Path) -> None:
    method = MethodAssemblyEvidence(
        owner="rLayout",
        method_name="load",
        signature="load()",
        definition_signature="void rLayout::load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        selected_function_name="rLayout::load()",
        selected_function_address=0x1000,
        selected_function_size=1,
        instructions=(OrbisInstruction(0x1000, "90", "nop", ""),),
    )
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256=_HEADER_BUNDLE_SHA256,
        status=ImplementationStatus.MATCHED,
        methods=(method,),
        header_files=("rLayout.h",),
    )

    path = AtomicImplementationReportPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        report,
        emit_sources=True,
        headers={"rLayout.h": "header"},
    )

    bundle = path.with_suffix("")
    assert not tuple(bundle.rglob("*.s"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["methods"][0]["source_artifact"]["generation_status"] == "not_eligible"
    assert payload["methods"][0]["source_artifact"]["diagnostics"] == [
        "implementation candidate is not unique"
    ]


@pytest.mark.unit
@pytest.mark.functional
def test_invalid_header_mapping_fails_before_staging(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="header mapping is missing generated files"):
        AtomicImplementationReportPublisher().publish(
            tmp_path,
            ELFPlatform.PS4,
            1,
            "rLayout",
            _source_report(),
            emit_sources=True,
            headers={"other.h": "header"},
        )

    implementation_dir = tmp_path / "ps4" / "implementations"
    assert not tuple(implementation_dir.glob(".*staging-*"))


@pytest.mark.unit
@pytest.mark.functional
def test_missing_header_mapping_fails_before_staging(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires the generated header mapping"):
        AtomicImplementationReportPublisher().publish(
            tmp_path,
            ELFPlatform.PS4,
            1,
            "rLayout",
            _source_report(),
            emit_sources=True,
        )

    implementation_dir = tmp_path / "ps4" / "implementations"
    assert not tuple(implementation_dir.glob(".*staging-*"))


@pytest.mark.unit
@pytest.mark.functional
def test_mismatched_header_content_fails_before_staging(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="header mapping content does not match"):
        AtomicImplementationReportPublisher().publish(
            tmp_path,
            ELFPlatform.PS4,
            1,
            "rLayout",
            _source_report(),
            emit_sources=True,
            headers={"rLayout.h": "different header"},
        )

    implementation_dir = tmp_path / "ps4" / "implementations"
    assert not tuple(implementation_dir.glob(".*staging-*"))


@pytest.mark.unit
@pytest.mark.functional
def test_invalid_renderer_hash_leaves_no_published_bundle(tmp_path: Path) -> None:
    publisher = AtomicImplementationReportPublisher(renderer=_BadArtifactRenderer())

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        publisher.publish(
            tmp_path,
            ELFPlatform.PS4,
            1,
            "rLayout",
            _source_report(),
            emit_sources=True,
            headers={"rLayout.h": "header"},
        )

    implementation_dir = tmp_path / "ps4" / "implementations"
    assert not tuple(implementation_dir.glob("*.json"))
    assert not tuple(implementation_dir.glob(".*staging-*"))


@pytest.mark.unit
@pytest.mark.functional
def test_report_only_publication_retires_previous_source_bundle(tmp_path: Path) -> None:
    method = MethodAssemblyEvidence(
        owner="rLayout",
        method_name="load",
        signature="load()",
        definition_signature="void rLayout::load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        selected_function_name="rLayout::load()",
        selected_function_address=0x1000,
        selected_function_size=1,
        instructions=(OrbisInstruction(0x1000, "90", "nop", "", "rLayout.cpp", 10),),
    )
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256=_HEADER_BUNDLE_SHA256,
        status=ImplementationStatus.MATCHED,
        methods=(method,),
        header_files=("rLayout.h",),
    )
    publisher = AtomicImplementationReportPublisher()
    report_path = publisher.publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        report,
        emit_sources=True,
        headers={"rLayout.h": "header"},
    )
    bundle = report_path.with_suffix("")
    assert bundle.exists()

    publisher.publish(tmp_path, ELFPlatform.PS4, 1, "rLayout", report)

    assert not bundle.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["source_status"] == "not_requested"
    assert list(report_path.parent.glob("*.tmp")) == []


@pytest.mark.unit
@pytest.mark.functional
def test_duplicate_method_ids_leave_previous_bundle_untouched(tmp_path: Path) -> None:
    method = MethodAssemblyEvidence(
        owner="rLayout",
        method_name="load",
        signature="load()",
        definition_signature="void rLayout::load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        selected_function_name="rLayout::load()",
        selected_function_address=0x1000,
        selected_function_size=1,
        instructions=(OrbisInstruction(0x1000, "90", "nop", "", "rLayout.cpp", 10),),
    )
    valid = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256=_HEADER_BUNDLE_SHA256,
        status=ImplementationStatus.MATCHED,
        methods=(method,),
        header_files=("rLayout.h",),
    )
    publisher = AtomicImplementationReportPublisher()
    report_path = publisher.publish(
        tmp_path,
        ELFPlatform.PS4,
        1,
        "rLayout",
        valid,
        emit_sources=True,
        headers={"rLayout.h": "header"},
    )
    before = report_path.read_bytes()
    duplicate = valid.__class__(
        root_symbol=valid.root_symbol,
        header_bundle_sha256=valid.header_bundle_sha256,
        status=valid.status,
        methods=(method, method),
        header_files=valid.header_files,
    )

    with pytest.raises(ValueError, match="duplicate implementation method id"):
        publisher.publish(
            tmp_path,
            ELFPlatform.PS4,
            1,
            "rLayout",
            duplicate,
            emit_sources=True,
            headers={"rLayout.h": "header"},
        )

    assert report_path.read_bytes() == before
    assert report_path.with_suffix("").exists()

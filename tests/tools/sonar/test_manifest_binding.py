from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.sonar import validate_header_bundle as validator
from tools.sonar.msvc_validation.manifest_binding import CompilerHeader, inspect_manifest_binding

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _published_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "ps4-02020005"
    bundle = root / "rFoo"
    bundle.mkdir(parents=True)
    files = {"rFoo/rFoo.h": b"class rFoo {};\n", "rFoo/Dependency.h": b"class Dependency {};\n"}
    for name, content in files.items():
        (root / name).write_bytes(content)
    manifest = {
        "header_count": len(files),
        "file_hashes": {
            name: {
                "kind": "header",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            for name, content in files.items()
        },
    }
    (root / "symbols.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _binding(root: Path) -> dict:
    headers = [
        CompilerHeader(path, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size)
        for path in root.rglob("*.h")
    ]
    return inspect_manifest_binding(headers, [root])


def test_manifest_binding_matches_only_complete_unchanged_publication(tmp_path: Path) -> None:
    root = _published_bundle(tmp_path)

    assert _binding(root)["status"] == "matched"

    (root / "rFoo" / "Dependency.h").unlink()
    missing = _binding(root)
    assert missing["status"] == "mismatch"
    assert missing["expected_header_count"] == 2
    assert any("was not attempted" in item for item in missing["diagnostics"])


def test_manifest_binding_deduplicates_relative_and_resolved_manifest_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _published_bundle(tmp_path)
    monkeypatch.chdir(tmp_path)
    relative_root = Path(root.name)

    assert _binding(relative_root)["status"] == "matched"


def test_manifest_binding_rejects_changed_and_unlisted_headers(tmp_path: Path) -> None:
    root = _published_bundle(tmp_path)
    (root / "rFoo" / "rFoo.h").write_text("class rFoo { int x; };\n", encoding="utf-8")
    (root / "rFoo" / "Extra.h").write_text("class Extra {};\n", encoding="utf-8")

    report = _binding(root)

    assert report["status"] == "mismatch"
    assert any("hash or size differs" in item for item in report["diagnostics"])
    assert any("no publication record" in item for item in report["diagnostics"])


def test_successful_compiler_markers_cannot_hide_missing_published_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _published_bundle(tmp_path)
    (root / "rFoo" / "Dependency.h").unlink()
    monkeypatch.setattr(validator, "get_visual_studio_developer_command_file", lambda: tmp_path)
    monkeypatch.setattr(validator, "test_msvc_toolchain", lambda _: "cl.exe")
    monkeypatch.setattr(validator, "_compiler_metadata", lambda _: {})

    def fake_run(script: Path, _timeout: int) -> tuple[int, str, bool]:
        objects = script.parent / "objects"
        objects.mkdir(exist_ok=True)
        (objects / "u00001.obj").write_bytes(b"object")
        (objects / "compile_all.obj").write_bytes(b"object")
        return 0, "DDON_HEADER_RESULT|u00001|0\nDDON_AGGREGATE_RESULT|compile_all.cpp|0\n", False

    monkeypatch.setattr(validator, "_run_script", fake_run)
    report = validator.run_validation([root], tmp_path / "validation", 10)

    assert report["counts"]["passed"] == 1
    assert report["aggregate_status"] == "passed"
    assert report["publication"]["status"] == "mismatch"
    assert report["status"] == "partial"


def test_skipped_unit_cannot_pass_with_valid_manifest_and_aggregate_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _published_bundle(tmp_path)
    monkeypatch.setattr(validator, "get_visual_studio_developer_command_file", lambda: tmp_path)
    monkeypatch.setattr(validator, "test_msvc_toolchain", lambda _: "cl.exe")
    monkeypatch.setattr(validator, "_compiler_metadata", lambda _: {})

    def fake_run(script: Path, _timeout: int) -> tuple[int, str, bool]:
        objects = script.parent / "objects"
        objects.mkdir(exist_ok=True)
        (objects / "u00001.obj").write_bytes(b"object")
        (objects / "compile_all.obj").write_bytes(b"object")
        return 0, "DDON_HEADER_RESULT|u00001|0\nDDON_AGGREGATE_RESULT|compile_all.cpp|0\n", False

    monkeypatch.setattr(validator, "_run_script", fake_run)
    report = validator.run_validation([root], tmp_path / "validation", 10)

    assert report["publication"]["status"] == "matched"
    assert report["counts"]["not_observed"] == 1
    assert report["aggregate_status"] == "passed"
    assert report["status"] == "partial"

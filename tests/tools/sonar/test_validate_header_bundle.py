from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.sonar import validate_header_bundle as validator
from tools.sonar.msvc_validation.commands import CommandExecution

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "symbols" / "0001-rFoo" / "ps4"
    bundle.mkdir(parents=True)
    (bundle / "rFoo.h").write_text('#include "Dependency.h"\nclass rFoo {};\n', encoding="utf-8")
    (bundle / "Dependency.h").write_text("class Dependency {};\n", encoding="utf-8")
    return bundle


def test_discover_units_preserves_bundle_context_and_writes_isolated_sources(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)

    bundles, units = validator.discover_units([tmp_path], tmp_path / "validation")

    assert bundles == [bundle]
    assert [unit.key for unit in units] == ["u00001", "u00002"]
    assert units[0].translation_unit.read_text(encoding="utf-8") == ('#include "Dependency.h"\n')
    assert units[1].bundle == bundle


def test_validation_script_reports_standalone_and_aggregate_units(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _, units = validator.discover_units([bundle], tmp_path / "validation")

    script = validator.write_validation_script(
        tmp_path / "validation", tmp_path / "VsDevCmd.bat", units
    )
    text = script.read_text(encoding="utf-8")

    assert "compile_all.cpp" in text
    assert "DDON_HEADER_RESULT^|u00001^|!UNIT_EXIT!" in text
    assert "DDON_AGGREGATE_RESULT^|compile_all.cpp^|!AGGREGATE_EXIT!" in text
    assert '/I"' + str(bundle) + '"' in text


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ([], "compile_error"),
        (["C2065"], "unresolved_identifier_or_type"),
        (["C2143"], "unresolved_identifier_or_type"),
        (["C2011"], "syntax_or_compile_error"),
    ],
)
def test_classify_failure(codes: list[str], expected: str) -> None:
    assert validator._classify_failure(codes) == expected


def test_run_validation_records_unobserved_units_and_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    developer = tmp_path / "VsDevCmd.bat"
    developer.write_text("", encoding="utf-8")
    monkeypatch.setattr(validator, "get_visual_studio_developer_command_file", lambda: developer)
    monkeypatch.setattr(validator, "test_msvc_toolchain", lambda _: r"C:\MSVC\cl.exe")

    def fake_run(script: Path, timeout: int) -> tuple[int, str, bool]:
        del timeout
        object_path = script.parent / "objects" / "u00001.obj"
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(b"object")
        return 0, "DDON_HEADER_RESULT|u00001|0\n", False

    monkeypatch.setattr(validator, "_run_script", fake_run)

    report = validator.run_validation([bundle], tmp_path / "validation", 10)

    assert report["header_count"] == 2
    assert report["counts"] == {
        "failed": 0,
        "not_observed": 1,
        "passed": 1,
        "timed_out": 0,
    }
    assert report["standalone_status"] == "partial"
    assert report["aggregate_status"] == "not_observed"
    assert report["status"] == "partial"
    assert report["validation_scope"] == "season2_header_closures"
    assert report["msvc_unit_count"] == 2
    saved = json.loads(
        (tmp_path / "validation" / "msvc-header-validation.json").read_text(encoding="utf-8")
    )
    assert saved["units"][0]["status"] == "passed"
    assert saved["units"][1]["failure_class"] == "incomplete"
    assert saved["units"][0]["object_status"] == "present"


def test_timeout_is_incomplete_not_success(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _, units = validator.discover_units([bundle], tmp_path / "validation")
    result = validator._unit_result(units[0], None, True)

    assert result["status"] == "timed_out"
    assert result["failure_class"] == "incomplete"


def test_run_script_rejects_truncated_markers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        validator,
        "run_command",
        lambda *_args, **_kwargs: CommandExecution(
            0,
            "partial",
            "",
            stdout_truncated=True,
        ),
    )

    with pytest.raises(validator.SonarAnalysisError, match="truncated"):
        validator._run_script(tmp_path / "compile.cmd", 10)


def test_compiler_metadata_and_aggregate_status_are_independent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compiler = tmp_path / "cl.exe"
    compiler.write_bytes(b"compiler")
    monkeypatch.setattr(
        validator,
        "run_command",
        lambda _command, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="Microsoft (R) C/C++ Optimizing Compiler Version 19.51\n",
            stderr="",
            output="Microsoft (R) C/C++ Optimizing Compiler Version 19.51\n",
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
        ),
    )

    metadata = validator._compiler_metadata(str(compiler))

    assert metadata["compiler_path"] == str(compiler)
    assert metadata["compiler_version_status"] == "observed"
    assert "19.51" in str(metadata["compiler_version"])
    assert metadata["compiler_sha256"]
    validation_directory = tmp_path / "validation"
    object_file = validation_directory / "objects" / "compile_all.obj"
    object_file.parent.mkdir(parents=True)
    object_file.write_bytes(b"object")
    (validation_directory / "diagnostics").mkdir(parents=True)
    (validation_directory / "diagnostics" / "compile_all.stdout.log").write_text(
        "", encoding="utf-8"
    )
    (validation_directory / "diagnostics" / "compile_all.stderr.log").write_text(
        "", encoding="utf-8"
    )

    aggregate = validator._aggregate_result(validation_directory, 0, False)

    assert aggregate["status"] == "passed"
    assert aggregate["object_status"] == "present"


def test_compiler_metadata_rejects_truncated_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compiler = tmp_path / "cl.exe"
    compiler.write_bytes(b"compiler")
    monkeypatch.setattr(
        validator,
        "run_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="prefix",
            stderr="",
            output="prefix",
            timed_out=False,
            stdout_truncated=True,
            stderr_truncated=False,
        ),
    )

    metadata = validator._compiler_metadata(str(compiler))

    assert metadata["compiler_version_status"] == "not_observed"
    assert metadata["compiler_version"] is None


def test_main_fails_when_aggregate_compilation_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = {
        "compiler_path": "cl.exe",
        "compiler_version": "19.51",
        "bundle_count": 1,
        "header_count": 2,
        "process_exit_code": 1,
        "process_timed_out": False,
        "counts": {"failed": 0, "not_observed": 0, "passed": 2, "timed_out": 0},
        "standalone_status": "observed",
        "aggregate_status": "failed",
        "status": "partial",
        "failure_classes": {},
        "diagnostic_code_counts": {},
    }
    monkeypatch.setattr(validator, "run_validation", lambda *_args: report)

    exit_code = validator.main(
        [
            "--input-root",
            str(tmp_path / "input"),
            "--validation-directory",
            str(tmp_path / "validation"),
        ]
    )

    assert exit_code == 1


def test_unit_result_records_separate_diagnostics_and_missing_object(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _, units = validator.discover_units([bundle], tmp_path / "validation")
    unit = units[0]
    unit.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    unit.stdout_log.write_text("cl.exe output\n", encoding="utf-8")
    unit.stderr_log.write_text("warning C4201\n", encoding="utf-8")

    result = validator._unit_result(unit, 0, False)

    assert result["status"] == "failed"
    assert result["failure_class"] == "object_missing"
    assert result["stdout_sha256"] != result["stderr_sha256"]
    assert result["diagnostic_codes"] == ["C4201"]


def test_discover_bundles_supports_versioned_symbol_directories(tmp_path: Path) -> None:
    version_root = tmp_path / "ps4-02020005"
    symbol_dir = version_root / "rFoo"
    shared_dir = version_root / "shared"
    symbol_dir.mkdir(parents=True)
    shared_dir.mkdir(parents=True)
    (symbol_dir / "rFoo.h").write_text("class rFoo {};\n", encoding="utf-8")
    (shared_dir / "MtObject.h").write_text("class MtObject {};\n", encoding="utf-8")

    bundles = validator.discover_bundles(version_root)

    assert bundles == [symbol_dir, shared_dir]


def test_write_validation_script_uses_response_file_for_large_include_sets(tmp_path: Path) -> None:
    # Create 30 bundles with long names to exceed 2048 chars
    bundles: list[Path] = []
    for i in range(30):
        long_name = f"very_long_bundle_name_segment_to_exceed_command_line_budget_{i:03d}"
        bundle = tmp_path / long_name
        bundle.mkdir(parents=True)
        (bundle / f"header_{i:03d}.h").write_text("class Foo {};\n", encoding="utf-8")
        bundles.append(bundle)

    _, units = validator.discover_units(bundles, tmp_path / "validation")
    script = validator.write_validation_script(
        tmp_path / "validation", tmp_path / "VsDevCmd.bat", units
    )
    text = script.read_text(encoding="utf-8")
    rsp_path = tmp_path / "validation" / "translation-units" / "compile_all.rsp"

    assert rsp_path.is_file()
    assert (
        "@%ROOT%translation-units\\compile_all.rsp" in text
        or '@"%ROOT%translation-units\\compile_all.rsp"' in text
    )
    rsp_text = rsp_path.read_text(encoding="utf-8")
    assert f'/I"{bundles[0]}"' in rsp_text

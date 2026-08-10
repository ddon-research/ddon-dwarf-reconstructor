from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sonar import validate_header_bundle as validator

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


def test_validation_script_compiles_each_unit_without_aggregate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _, units = validator.discover_units([bundle], tmp_path / "validation")

    script = validator.write_validation_script(
        tmp_path / "validation", tmp_path / "VsDevCmd.bat", units
    )
    text = script.read_text(encoding="utf-8")

    assert "compile_all.cpp" not in text
    assert "DDON_HEADER_RESULT^|u00001^|!UNIT_EXIT!" in text
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
    monkeypatch.setattr(
        validator,
        "_run_script",
        lambda script, timeout: (0, "DDON_HEADER_RESULT|u00001|0\n", False),
    )

    report = validator.run_validation([bundle], tmp_path / "validation", 10)

    assert report["header_count"] == 2
    assert report["counts"] == {"passed": 1, "not_observed": 1}
    saved = json.loads(
        (tmp_path / "validation" / "msvc-header-validation.json").read_text(encoding="utf-8")
    )
    assert saved["units"][0]["status"] == "passed"
    assert saved["units"][1]["failure_class"] == "incomplete"


def test_timeout_is_incomplete_not_success(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _, units = validator.discover_units([bundle], tmp_path / "validation")
    result = validator._unit_result(units[0], None, True)

    assert result["status"] == "timed_out"
    assert result["failure_class"] == "incomplete"

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.sonar import prepare_msvc_analysis as sonar

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _paths(tmp_path: Path) -> sonar.SonarPaths:
    validation = tmp_path / "validation"
    validation.mkdir()
    headers = validation / "ps4"
    headers.mkdir()
    script = validation / "compile_msvc.cmd"
    return sonar.SonarPaths(
        repository_root=tmp_path,
        validation_directory=validation,
        header_directory=headers,
        translation_unit_directory=validation / "translation-units",
        validation_script=script,
        output_directory=tmp_path / "wrapper",
    )


def _toolchain(tmp_path: Path) -> sonar.Toolchain:
    wrapper = tmp_path / "build-wrapper-win-x86-64.exe"
    developer = tmp_path / "VsDevCmd.bat"
    wrapper.write_text("", encoding="utf-8")
    developer.write_text("", encoding="utf-8")
    return sonar.Toolchain(wrapper, developer, r"C:\MSVC\bin\cl.exe")


def _compile_commands(path: Path, *, flags: bool = True) -> None:
    command = "cl.exe /std:c++latest /EHsc /W4 /Zc:__cplusplus" if flags else "cl.exe"
    path.write_text(
        json.dumps([{"file": "generated.cpp", "command": command}]),
        encoding="utf-8",
    )


def test_build_wrapper_arguments_preserve_windows_command_flow(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    toolchain = _toolchain(tmp_path)

    arguments = sonar.build_wrapper_arguments(paths, toolchain)

    assert arguments[:3] == [str(toolchain.build_wrapper), "--out-dir", str(paths.output_directory)]
    assert arguments[3:] == [
        "cmd.exe",
        "/d",
        "/c",
        "call",
        str(toolchain.developer_command_file),
        "-arch=x64",
        "&&",
        "cd",
        "/d",
        str(paths.validation_directory),
        "&&",
        "call",
        str(paths.validation_script),
    ]


def test_visual_studio_discovery_reports_missing_locator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)

    with pytest.raises(sonar.SonarAnalysisError, match="Program Files"):
        sonar.get_visual_studio_developer_command_file()


def test_msvc_probe_uses_cmd_and_returns_compiler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    developer = tmp_path / "VsDevCmd.bat"
    developer.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout=r"C:\MSVC\bin\cl.exe" + "\n",
            stderr="",
        )

    monkeypatch.setattr(sonar, "_run_command", fake_run)

    compiler = sonar.test_msvc_toolchain(developer)

    assert compiler.endswith("cl.exe")
    assert calls == [
        [
            "cmd.exe",
            "/d",
            "/c",
            "call",
            str(developer),
            "-arch=x64",
            "&&",
            "where",
            "cl",
        ]
    ]


def test_compile_commands_require_cpp_unit_and_msvc_flags(tmp_path: Path) -> None:
    report = tmp_path / "compile_commands.json"
    _compile_commands(report)

    assert sonar.validate_compile_commands(report) == (1, 1)

    _compile_commands(report, flags=False)
    with pytest.raises(sonar.SonarAnalysisError, match="expected MSVC flags"):
        sonar.validate_compile_commands(report)


def test_compile_commands_reject_malformed_json(tmp_path: Path) -> None:
    report = tmp_path / "compile_commands.json"
    report.write_text("not-json", encoding="utf-8")

    with pytest.raises(sonar.SonarAnalysisError, match="Could not read compilation database"):
        sonar.validate_compile_commands(report)


def test_prepare_validation_inputs_generates_sources_command_and_manifest(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    (paths.header_directory / "rTexture.h").write_text("class rTexture {};\n", encoding="utf-8")
    (paths.header_directory / "rTutorialDialogMessage.h").write_text(
        "class rTutorialDialogMessage {};\n", encoding="utf-8"
    )

    inputs = sonar.prepare_validation_inputs(paths)

    assert inputs.header_count == 2
    assert inputs.translation_unit_count == 2
    assert (paths.translation_unit_directory / "compile_rTexture.cpp").read_text(
        encoding="utf-8"
    ) == '#include "rTexture.h"\n'
    assert (paths.translation_unit_directory / "compile_tutorial.cpp").read_text(
        encoding="utf-8"
    ) == '#include "rTutorialDialogMessage.h"\n'
    aggregate = (paths.translation_unit_directory / "compile_all.cpp").read_text(encoding="utf-8")
    assert aggregate.index('#include "rTexture.h"') < aggregate.index(
        '#include "rTutorialDialogMessage.h"'
    )
    script = paths.validation_script.read_text(encoding="utf-8")
    assert "/std:c++latest /EHsc /W4 /Zc:__cplusplus" in script
    assert "compile_tutorial.cpp" in script
    assert "compile_all.cpp" in script
    manifest = json.loads(inputs.manifest_path.read_text(encoding="utf-8"))
    assert manifest["translation_units"] == [
        "compile_rTexture.cpp",
        "compile_tutorial.cpp",
    ]
    assert manifest["aggregate_translation_unit"] == "compile_all.cpp"
    assert manifest["headers"][0]["path"] == "rTexture.h"


def test_prepare_validation_inputs_requires_generated_headers(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    with pytest.raises(sonar.SonarAnalysisError, match=r"No generated C\+\+ headers"):
        sonar.prepare_validation_inputs(paths)


def test_validate_only_reports_configuration_without_creating_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    toolchain = _toolchain(tmp_path)

    assert sonar.validate_only(paths, toolchain) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["validation_only"] is True
    assert not paths.output_directory.exists()


def test_capture_database_reports_success_and_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    toolchain = _toolchain(tmp_path)
    calls: list[list[str]] = []

    def fake_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        paths.output_directory.mkdir(parents=True, exist_ok=True)
        _compile_commands(paths.output_directory / "compile_commands.json")
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    monkeypatch.setattr(sonar, "_run_command", fake_run)

    assert sonar.capture_database(paths, toolchain, allow_validation_failure=False) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["translation_unit_count"] == 1
    assert output["msvc_flag_entry_count"] == 1
    assert calls == [sonar.build_wrapper_arguments(paths, toolchain)]


def test_capture_database_can_report_allowed_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _paths(tmp_path)
    toolchain = _toolchain(tmp_path)

    def fake_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        paths.output_directory.mkdir(parents=True, exist_ok=True)
        _compile_commands(paths.output_directory / "compile_commands.json")
        return subprocess.CompletedProcess(arguments, 7, stdout="", stderr="")

    monkeypatch.setattr(sonar, "_run_command", fake_run)

    assert sonar.capture_database(paths, toolchain, allow_validation_failure=True) == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["validation_exit_code"] == 7
    assert "validating the captured database anyway" in captured.err


def test_capture_database_rejects_strict_validation_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    toolchain = _toolchain(tmp_path)

    monkeypatch.setattr(
        sonar,
        "_run_command",
        lambda arguments: subprocess.CompletedProcess(arguments, 7, stdout="", stderr=""),
    )

    with pytest.raises(sonar.SonarAnalysisError, match="failed with exit code 7"):
        sonar.capture_database(paths, toolchain, allow_validation_failure=False)

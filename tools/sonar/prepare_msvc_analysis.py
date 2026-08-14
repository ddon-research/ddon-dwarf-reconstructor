"""Prepare a SonarQube C/C++ compilation database on Windows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .msvc_validation.publication import write_json_atomic

REQUIRED_MSVC_FLAGS = ("/std:c++latest", "/EHsc", "/W4", "/Zc:__cplusplus")
TRANSLATION_UNIT_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
AGGREGATE_TRANSLATION_UNIT = "compile_all.cpp"
DEFAULT_VALIDATION_DIRECTORY = Path("output/msvc-header-validation-20260801")


class SonarAnalysisError(RuntimeError):
    """Raised when the local Sonar or MSVC prerequisites are invalid."""


@dataclass(frozen=True, slots=True)
class SonarPaths:
    repository_root: Path
    validation_directory: Path
    header_directory: Path
    translation_unit_directory: Path
    validation_script: Path
    output_directory: Path


@dataclass(frozen=True, slots=True)
class Toolchain:
    build_wrapper: Path
    developer_command_file: Path
    compiler: str


@dataclass(frozen=True, slots=True)
class ValidationInputs:
    """Generated source inputs consumed by MSVC and Sonar Build Wrapper."""

    header_count: int
    translation_unit_count: int
    manifest_path: Path


def resolve_existing_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SonarAnalysisError(f"Could not find {description} at '{path}'.")
    return resolved


def resolve_existing_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SonarAnalysisError(f"Could not find {description} at '{path}'.")
    return resolved


def get_build_wrapper_file(requested_path: Path | None) -> Path:
    if requested_path is not None:
        return resolve_existing_file(requested_path, "Sonar Build Wrapper")

    candidates: list[Path] = []
    path_command = shutil.which("build-wrapper-win-x86-64.exe")
    if path_command:
        candidates.append(Path(path_command))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data)
            / "SonarSource"
            / "build-wrapper-win-x86"
            / "build-wrapper-win-x86"
            / "build-wrapper-win-x86-64.exe"
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SonarAnalysisError(
        "Sonar Build Wrapper was not found. Use --build-wrapper-path with "
        "build-wrapper-win-x86-64.exe."
    )


def _run_command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(arguments, capture_output=True, text=True, check=False)
    except OSError as error:
        raise SonarAnalysisError(f"Could not run {arguments[0]!r}: {error}") from error


def get_visual_studio_developer_command_file() -> Path:
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    if not program_files_x86:
        raise SonarAnalysisError("The Program Files (x86) environment variable is not available.")

    vswhere_path = resolve_existing_file(
        Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        "Visual Studio installer locator",
    )
    result = _run_command(
        [
            str(vswhere_path),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ]
    )
    if result.returncode != 0:
        raise SonarAnalysisError(
            f"vswhere.exe failed with exit code {result.returncode}. "
            f"Output: {(result.stdout + result.stderr).strip()}"
        )

    installation_path = next(
        (line.strip() for line in result.stdout.splitlines() if line.strip()), ""
    )
    if not installation_path:
        raise SonarAnalysisError(
            "vswhere.exe found no Visual Studio installation with the C++ x64 toolchain."
        )
    return resolve_existing_file(
        Path(installation_path) / "Common7" / "Tools" / "VsDevCmd.bat",
        "Visual Studio developer command file",
    )


def test_msvc_toolchain(developer_command_file: Path) -> str:
    result = _run_command(
        [
            "cmd.exe",
            "/d",
            "/c",
            "call",
            str(developer_command_file),
            "-arch=x64",
            "&&",
            "where",
            "cl",
        ]
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise SonarAnalysisError(
            "Visual Studio x64 developer environment could not resolve cl.exe. "
            f"Output: {output.strip()}"
        )

    compiler = next(
        (
            line.strip()
            for line in output.splitlines()
            if re.search(r"[\\/]cl\.exe$", line.strip(), re.I)
        ),
        "",
    )
    if not compiler:
        raise SonarAnalysisError(
            "The Visual Studio x64 developer environment did not report cl.exe. "
            f"Output: {output.strip()}"
        )
    return compiler


def resolve_paths(
    validation_directory: Path | None,
    validation_script: str,
    output_directory: Path | None,
    header_directory: Path | None = None,
) -> SonarPaths:
    repository_root = Path(__file__).resolve().parents[2]
    validation = validation_directory or DEFAULT_VALIDATION_DIRECTORY
    if not validation.is_absolute():
        validation = repository_root / validation
    validation = resolve_existing_directory(validation, "MSVC validation directory")

    headers = header_directory or validation / "ps4"
    if not headers.is_absolute():
        headers = repository_root / headers
    headers = resolve_existing_directory(headers, "generated header directory")
    script_path = Path(validation_script)
    if not script_path.is_absolute():
        script_path = validation / script_path
    output = output_directory or validation / "sonar-build-wrapper"
    if not output.is_absolute():
        output = repository_root / output
    return SonarPaths(
        repository_root=repository_root,
        validation_directory=validation,
        header_directory=headers,
        translation_unit_directory=validation / "translation-units",
        validation_script=script_path.resolve(),
        output_directory=output.resolve(),
    )


def _header_files(paths: SonarPaths) -> list[Path]:
    headers = sorted(paths.header_directory.glob("*.h"), key=lambda path: path.name.lower())
    if not headers:
        raise SonarAnalysisError(
            f"No generated C++ headers were found in '{paths.header_directory}'."
        )
    return headers


def _translation_unit_name(header: Path) -> str:
    if header.name == "rTutorialDialogMessage.h":
        return "compile_tutorial.cpp"
    return f"compile_{header.stem}.cpp"


def _translation_unit_text(header: Path) -> str:
    return f'#include "{header.name}"\n'


def _aggregate_translation_unit_text(headers: list[Path]) -> str:
    includes = "".join(f'#include "{header.name}"\n' for header in headers)
    return f"// Generated by prepare_msvc_analysis.py.\n{includes}"


def _batch_include_path(header_directory: Path, validation_directory: Path) -> str:
    try:
        relative = header_directory.relative_to(validation_directory)
    except ValueError:
        return str(header_directory)
    return f"%ROOT%{str(relative).replace('/', '\\')}"


def _compile_script_text(source_names: list[str], aggregate_name: str, include_path: str) -> str:
    lines = [
        "@echo off",
        "setlocal EnableExtensions",
        'set "ROOT=%~dp0"',
        'if not exist "%ROOT%objects" mkdir "%ROOT%objects"',
        'set "EXIT_CODE=0"',
    ]
    for source_name in [*source_names, aggregate_name]:
        object_name = Path(source_name).with_suffix(".obj").name
        lines.extend(
            [
                "cl.exe /nologo /std:c++latest /EHsc /W4 /Zc:__cplusplus "
                f'/I"{include_path}" /c "%ROOT%translation-units\\{source_name}" '
                f'/Fo"%ROOT%objects\\{object_name}"',
                'if errorlevel 1 set "EXIT_CODE=1"',
            ]
        )
    lines.extend(["endlocal & exit /b %EXIT_CODE%", ""])
    return "\r\n".join(lines)


def _write_generated(path: Path, content: str, *, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline=newline)


def prepare_validation_inputs(paths: SonarPaths) -> ValidationInputs:
    """Generate deterministic translation units and the MSVC wrapper command."""
    headers = _header_files(paths)
    source_names = [_translation_unit_name(header) for header in headers]
    aggregate_name = AGGREGATE_TRANSLATION_UNIT
    if aggregate_name in source_names:
        raise SonarAnalysisError(
            "Generated header names collide with the aggregate translation unit"
        )
    for header, source_name in zip(headers, source_names, strict=True):
        _write_generated(
            paths.translation_unit_directory / source_name,
            _translation_unit_text(header),
        )
    _write_generated(
        paths.translation_unit_directory / aggregate_name,
        _aggregate_translation_unit_text(headers),
    )
    include_path = _batch_include_path(paths.header_directory, paths.validation_directory)
    _write_generated(
        paths.validation_script,
        _compile_script_text(source_names, aggregate_name, include_path),
        newline="\r\n",
    )
    manifest_path = paths.validation_directory / "sonar-inputs.json"
    manifest = {
        "schema_version": 1,
        "validation_scope": "aggregate_sonar_diagnostics",
        "headers": [
            {
                "path": header.name,
                "sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
            }
            for header in headers
        ],
        "translation_units": source_names,
        "header_file_count": len(headers),
        "msvc_unit_count": len(source_names),
        "aggregate_translation_unit_count": 1,
        "aggregate_translation_unit": aggregate_name,
        "validation_script": paths.validation_script.name,
    }
    write_json_atomic(manifest_path, manifest)
    return ValidationInputs(len(headers), len(source_names), manifest_path)


def resolve_toolchain(build_wrapper_path: Path | None) -> Toolchain:
    build_wrapper = get_build_wrapper_file(build_wrapper_path)
    developer_command_file = get_visual_studio_developer_command_file()
    compiler = test_msvc_toolchain(developer_command_file)
    return Toolchain(build_wrapper, developer_command_file, compiler)


def build_wrapper_arguments(paths: SonarPaths, toolchain: Toolchain) -> list[str]:
    return [
        str(toolchain.build_wrapper),
        "--out-dir",
        str(paths.output_directory),
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


def read_compile_commands(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SonarAnalysisError(
            f"Could not read compilation database '{path}': {error}"
        ) from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise SonarAnalysisError(
            f"Compilation database must contain a JSON array of objects: '{path}'."
        )
    return payload


def _compile_arguments(entry: dict[str, object]) -> str:
    arguments = entry.get("arguments")
    if isinstance(arguments, list):
        return " ".join(str(argument) for argument in arguments)
    command = entry.get("command")
    return command if isinstance(command, str) else ""


def validate_compile_commands(path: Path) -> tuple[int, int]:
    compile_commands = read_compile_commands(path)
    translation_units = [entry for entry in compile_commands if _is_translation_unit(entry)]
    if not translation_units:
        raise SonarAnalysisError(
            f"The compilation database contains no C/C++ translation-unit entries: '{path}'."
        )

    msvc_entries = [
        entry
        for entry in translation_units
        if all(flag in _compile_arguments(entry) for flag in REQUIRED_MSVC_FLAGS)
    ]
    if not msvc_entries:
        raise SonarAnalysisError(
            "The compilation database contains no translation unit with the expected MSVC flags."
        )
    return len(translation_units), len(msvc_entries)


def _is_translation_unit(entry: dict[str, object]) -> bool:
    file_name = entry.get("file")
    return (
        isinstance(file_name, str) and Path(file_name).suffix.lower() in TRANSLATION_UNIT_SUFFIXES
    )


def _result_json(result: dict[str, object]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def _input_result(inputs: ValidationInputs | None) -> dict[str, object]:
    if inputs is None:
        return {}
    return {
        "generated_header_count": inputs.header_count,
        "generated_translation_unit_count": inputs.translation_unit_count,
        "input_manifest_path": str(inputs.manifest_path),
    }


def validate_only(
    paths: SonarPaths,
    toolchain: Toolchain,
    inputs: ValidationInputs | None = None,
) -> int:
    _result_json(
        {
            "build_wrapper_path": str(toolchain.build_wrapper),
            "developer_command_file": str(toolchain.developer_command_file),
            "compiler_path": toolchain.compiler,
            "validation_script": str(paths.validation_script),
            "output_directory": str(paths.output_directory),
            "validation_only": True,
            **_input_result(inputs),
        }
    )
    return 0


def capture_database(
    paths: SonarPaths,
    toolchain: Toolchain,
    allow_validation_failure: bool,
    inputs: ValidationInputs | None = None,
) -> int:
    try:
        paths.output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SonarAnalysisError(
            f"Could not create Sonar Build Wrapper output directory '{paths.output_directory}': {error}"
        ) from error

    result = _run_command(build_wrapper_arguments(paths, toolchain))
    if result.returncode != 0 and not allow_validation_failure:
        raise SonarAnalysisError(
            "Sonar Build Wrapper or the MSVC validation command failed with exit code "
            f"{result.returncode}."
        )
    if result.returncode != 0:
        print(
            "Warning: the wrapped MSVC validation command failed with exit code "
            f"{result.returncode}; validating the captured database anyway.",
            file=sys.stderr,
        )

    compile_commands_path = resolve_existing_file(
        paths.output_directory / "compile_commands.json",
        "Sonar compilation database",
    )
    translation_unit_count, msvc_flag_entry_count = validate_compile_commands(compile_commands_path)
    _result_json(
        {
            "build_wrapper_path": str(toolchain.build_wrapper),
            "compile_commands_path": str(compile_commands_path),
            "compiler_path": toolchain.compiler,
            "translation_unit_count": translation_unit_count,
            "msvc_flag_entry_count": msvc_flag_entry_count,
            "validation_exit_code": result.returncode,
            "validation_only": False,
            **_input_result(inputs),
        }
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-wrapper-path", type=Path)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--validation-directory", type=Path)
    parser.add_argument("--header-directory", type=Path)
    parser.add_argument("--validation-script", default="compile_msvc.cmd")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--allow-validation-failure", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = resolve_paths(
            args.validation_directory,
            args.validation_script,
            args.output_directory,
            args.header_directory,
        )
        inputs = prepare_validation_inputs(paths)
        toolchain = resolve_toolchain(args.build_wrapper_path)
        if args.validate_only:
            return validate_only(paths, toolchain, inputs)
        return capture_database(paths, toolchain, args.allow_validation_failure, inputs)
    except SonarAnalysisError as error:
        print(f"Sonar analysis preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

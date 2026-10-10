"""Run small C++ declaration-order canaries with host MSVC and Clang."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    _repository_root = Path(__file__).resolve().parents[2]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))
    from tools.sonar.msvc_validation.commands import CommandExecution, run_command
    from tools.sonar.msvc_validation.failure_probe import _reference_identity
    from tools.sonar.msvc_validation.publication import write_json_atomic
    from tools.sonar.prepare_msvc_analysis import (
        get_visual_studio_developer_command_file,
        test_msvc_toolchain,
    )
else:
    from .msvc_validation.commands import CommandExecution, run_command
    from .msvc_validation.failure_probe import _reference_identity
    from .msvc_validation.publication import write_json_atomic
    from .prepare_msvc_analysis import (
        get_visual_studio_developer_command_file,
        test_msvc_toolchain,
    )

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "cpp" / "compiler_feedback"
CASES = {
    "grass-owner-first": False,
    "grass-specialization-first": False,
    "pawn-owner-first": False,
    "pawn-specialization-first": False,
    "allocator-ordered": True,
    "allocator-reversed": False,
    "nested-specialization-valid": True,
    "nested-member-primary-valid": True,
    "nested-generic-layout-valid": True,
}
EXPECTED_FAILURES = {
    "grass-owner-first": {"msvc": "C2079", "clang": "implicit instantiation of undefined template"},
    "grass-specialization-first": {"msvc": "C2027", "clang": "incomplete type 'rGrass'"},
    "pawn-owner-first": {"msvc": "C2079", "clang": "implicit instantiation of undefined template"},
    "pawn-specialization-first": {
        "msvc": "C2027",
        "clang": "incomplete type 'cPawnActInterDisableMgr'",
    },
    "allocator-reversed": {
        "msvc": "C2504",
        "clang": "implicit instantiation of undefined template",
    },
}
MODES = {"c++17": ("/std:c++17", "-std=c++17"), "c++23": ("/std:c++latest", "-std=c++23")}
MAX_OUTPUT = 512 * 1024


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool_identity(path: Path, version_flag: str) -> dict[str, str]:
    result = run_command([str(path), version_flag], timeout_seconds=30, max_output_bytes=MAX_OUTPUT)
    if result.timed_out or result.stdout_truncated or result.stderr_truncated:
        raise RuntimeError(f"Incomplete compiler version evidence for {path}")
    target = "x64-windows-msvc" if version_flag == "/Bv" else "unobserved"
    if version_flag != "/Bv":
        target = next(
            (
                line.partition(":")[2].strip()
                for line in result.output.splitlines()
                if line.startswith("Target:")
            ),
            "unobserved",
        )
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "version": result.output.strip()[:512],
        "target": target,
    }


def _msvc_script(path: Path, developer: Path, source: Path, mode: str) -> Path:
    script = path / "compile.cmd"
    script.write_text(
        "\r\n".join(
            [
                "@echo off",
                f'call "{developer}" -arch=x64',
                "if errorlevel 1 exit /b 9001",
                "echo DDON_CANARY_COMPILE_START",
                f"cl.exe /nologo {MODES[mode][0]} /EHsc /Zc:__cplusplus /c "
                f'"{source}" /Fo"{path / "canary.obj"}"',
                "",
            ]
        ),
        encoding="utf-8",
        newline="",
    )
    return script


def _save_execution(path: Path, execution: CommandExecution) -> dict[str, Any]:
    stdout = path / "stdout.log"
    stderr = path / "stderr.log"
    stdout.write_text(execution.stdout, encoding="utf-8")
    stderr.write_text(execution.stderr, encoding="utf-8")
    return {
        "exit_code": execution.returncode,
        "timed_out": execution.timed_out,
        "output_truncated": execution.stdout_truncated or execution.stderr_truncated,
        "stdout": str(stdout),
        "stdout_sha256": _sha256(stdout),
        "stderr": str(stderr),
        "stderr_sha256": _sha256(stderr),
    }


def _run_one(
    source: Path,
    name: str,
    mode: str,
    compiler: str,
    output: Path,
    developer: Path,
    clang: Path,
    timeout: int,
) -> dict[str, Any]:
    directory = output / name / mode / compiler
    directory.mkdir(parents=True, exist_ok=True)
    if compiler == "msvc":
        script = _msvc_script(directory, developer, source, mode)
        arguments = ["cmd.exe", "/d", "/c", "call", str(script)]
    else:
        arguments = [str(clang), MODES[mode][1], "-fsyntax-only", str(source)]
    execution = run_command(arguments, timeout_seconds=timeout, max_output_bytes=MAX_OUTPUT)
    observation = _save_execution(directory, execution)
    expected_pass = CASES[name]
    complete = not observation["timed_out"] and not observation["output_truncated"]
    if compiler == "msvc":
        complete = complete and "DDON_CANARY_COMPILE_START" in execution.output
    observed_pass = execution.returncode == 0
    expected_diagnostic = EXPECTED_FAILURES.get(name, {}).get(compiler)
    diagnostic_matches = expected_diagnostic is None or expected_diagnostic in execution.output
    observation.update(
        {
            "case": name,
            "mode": mode,
            "compiler": compiler,
            "source": str(source),
            "source_sha256": _sha256(source),
            "flags": [MODES[mode][0], "/EHsc", "/Zc:__cplusplus"]
            if compiler == "msvc"
            else [MODES[mode][1], "-fsyntax-only"],
            "expected_pass": expected_pass,
            "expected_diagnostic": expected_diagnostic,
            "status": "matched"
            if complete and observed_pass == expected_pass and diagnostic_matches
            else "mismatch",
        }
    )
    return observation


def _run_ast_probe(source: Path, clang: Path, output: Path) -> dict[str, Any]:
    path = output / "ast-probe"
    path.mkdir(parents=True, exist_ok=True)
    query = clang.with_name("clang-query.exe")
    if not query.is_file():
        return {"status": "unavailable", "reason": "clang-query.exe is absent"}
    commands = {
        "owner": [
            str(query),
            "-c",
            'match cxxRecordDecl(isDefinition(), hasName("Outer"))',
            str(source),
            "--",
            "-std=c++17",
        ],
        "layout": [
            str(clang),
            "-std=c++17",
            "-fsyntax-only",
            "-Xclang",
            "-fdump-record-layouts",
            str(source),
        ],
    }
    evidence = {}
    for name, arguments in commands.items():
        execution = run_command(arguments, timeout_seconds=30, max_output_bytes=MAX_OUTPUT)
        # Give each observation durable logs without retaining raw AST as a schema.
        (path / f"{name}.stdout.log").write_text(execution.stdout, encoding="utf-8")
        (path / f"{name}.stderr.log").write_text(execution.stderr, encoding="utf-8")
        evidence[name] = {
            "exit_code": execution.returncode,
            "timed_out": execution.timed_out,
            "output_truncated": execution.stdout_truncated or execution.stderr_truncated,
            "stdout": str(path / f"{name}.stdout.log"),
            "stdout_sha256": _sha256(path / f"{name}.stdout.log"),
            "stderr": str(path / f"{name}.stderr.log"),
            "stderr_sha256": _sha256(path / f"{name}.stderr.log"),
        }
    complete = all(
        item["exit_code"] == 0 and not item["timed_out"] and not item["output_truncated"]
        for item in evidence.values()
    )
    complete = complete and "1 match." in (path / "owner.stdout.log").read_text(encoding="utf-8")
    complete = complete and "Tree<struct Outer::Inner>" in (path / "layout.stdout.log").read_text(
        encoding="utf-8"
    )
    return {"status": "observed" if complete else "partial", "queries": evidence}


def run_canaries(output: Path, reference: Path, clang: Path, timeout: int = 60) -> dict[str, Any]:
    """Keep all compiler objects and logs outside the tracked fixture directory."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reference_identity = _reference_identity(reference.resolve())
    developer = get_visual_studio_developer_command_file()
    msvc = Path(test_msvc_toolchain(developer)).resolve()
    if not clang.is_file():
        raise FileNotFoundError(clang)
    tools = {"msvc": _tool_identity(msvc, "/Bv"), "clang": _tool_identity(clang, "--version")}
    results = [
        _run_one(FIXTURES / f"{name}.cpp", name, mode, compiler, output, developer, clang, timeout)
        for name in CASES
        for mode in MODES
        for compiler in tools
    ]
    ast = _run_ast_probe(FIXTURES / "nested-specialization-valid.cpp", clang, output)
    report = {
        "schema_version": 1,
        "tool_sha256": _sha256(Path(__file__)),
        "reference": reference_identity,
        "fixture_inputs": {
            path.name: _sha256(path)
            for path in sorted(FIXTURES.iterdir())
            if path.suffix in {".cpp", ".h"}
        },
        "compilers": tools,
        "results": results,
        "ast_probe": ast,
        "status": "matched"
        if all(item["status"] == "matched" for item in results) and ast["status"] == "observed"
        else "partial",
    }
    write_json_atomic(output / "declaration-canaries.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, default=Path("D:/research/cppstdmd"))
    parser.add_argument("--clang", type=Path, default=Path("C:/msys64/clang64/bin/clang++.exe"))
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        report = run_canaries(
            args.output_dir, args.reference_root, args.clang, args.timeout_seconds
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Declaration canary run failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "case_count": len(report["results"]),
                "ast_probe": report["ast_probe"]["status"],
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "matched" else 1


if __name__ == "__main__":
    raise SystemExit(main())

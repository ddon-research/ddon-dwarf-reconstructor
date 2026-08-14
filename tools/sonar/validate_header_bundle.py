"""Compile every generated header closure individually with MSVC on Windows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    # Keep the established ``python tools/sonar/validate_header_bundle.py``
    # launcher usable while retaining package-relative imports for normal use.
    _repository_root = Path(__file__).resolve().parents[2]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))
    from tools.sonar.msvc_validation.catalog import build_header_catalog
    from tools.sonar.msvc_validation.commands import run_command
    from tools.sonar.msvc_validation.publication import write_json_atomic
    from tools.sonar.msvc_validation.reports import validation_counts
    from tools.sonar.prepare_msvc_analysis import (
        SonarAnalysisError,
        get_visual_studio_developer_command_file,
        test_msvc_toolchain,
    )
else:
    from .msvc_validation.catalog import build_header_catalog
    from .msvc_validation.commands import run_command
    from .msvc_validation.publication import write_json_atomic
    from .msvc_validation.reports import validation_counts
    from .prepare_msvc_analysis import (
        SonarAnalysisError,
        get_visual_studio_developer_command_file,
        test_msvc_toolchain,
    )

MSVC_FLAGS = ("/std:c++latest", "/EHsc", "/W4", "/Zc:__cplusplus")
DIAGNOSTIC_CODE = re.compile(r"\b([CE]\d{4})\b", re.IGNORECASE)
UNRESOLVED_CODES = frozenset(
    {
        "C2061",  # syntax error: identifier
        "C2065",  # undeclared identifier
        "C2143",  # missing token, often caused by an unresolved type
        "C2146",  # missing token before an undeclared identifier
        "C2653",  # identifier is not a class or namespace name
        "C3646",  # unknown override specifier / type-like token
        "C3861",  # identifier not found
        "C4430",  # missing type specifier
    }
)


class HeaderValidationError(RuntimeError):
    """Raised when a complete per-header validation cannot be prepared."""


@dataclass(frozen=True, slots=True)
class HeaderUnit:
    """One generated header and its isolated translation unit."""

    sequence: int
    bundle: Path
    header: Path
    translation_unit: Path
    object_file: Path
    diagnostic_log: Path
    header_sha256: str
    header_bytes: int

    @property
    def key(self) -> str:
        return f"u{self.sequence:05d}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise HeaderValidationError(f"Could not find {description} at '{path}'.")
    return resolved


def discover_bundles(input_root: Path) -> list[Path]:
    """Discover symbol ``ps4`` directories deterministically."""
    root = _resolve_directory(input_root, "header input root")
    if root.name.lower() == "ps4" and any(root.glob("*.h")):
        return [root]
    if any(root.glob("*.h")):
        return [root]
    bundles = sorted(
        (path for path in root.rglob("ps4") if path.is_dir() and any(path.glob("*.h"))),
        key=lambda path: str(path).lower(),
    )
    if not bundles:
        raise HeaderValidationError(f"No generated header bundles were found below '{root}'.")
    return bundles


def _write_unit(unit: HeaderUnit) -> None:
    unit.translation_unit.parent.mkdir(parents=True, exist_ok=True)
    unit.translation_unit.write_text(
        f'#include "{unit.header.name}"\n',
        encoding="utf-8",
        newline="\n",
    )


def discover_units(
    input_roots: list[Path], validation_directory: Path
) -> tuple[list[Path], list[HeaderUnit]]:
    """Discover every header path and create one isolated source file per header."""
    bundles: list[Path] = []
    for root in input_roots:
        bundles.extend(discover_bundles(root))
    bundles = sorted(set(bundles), key=lambda path: str(path).lower())
    try:
        catalog = build_header_catalog(bundles)
    except ValueError as error:
        raise HeaderValidationError(str(error)) from error
    units: list[HeaderUnit] = []
    for sequence, entry in enumerate(catalog.entries, start=1):
        bundle = entry.bundle
        unit = HeaderUnit(
            sequence=sequence,
            bundle=bundle,
            header=entry.header,
            translation_unit=validation_directory / "translation-units" / f"u{sequence:05d}.cpp",
            object_file=validation_directory / "objects" / f"u{sequence:05d}.obj",
            diagnostic_log=validation_directory / "diagnostics" / f"u{sequence:05d}.log",
            header_sha256=entry.sha256,
            header_bytes=entry.byte_count,
        )
        _write_unit(unit)
        units.append(unit)
    if not units:
        raise HeaderValidationError("No generated headers were found in the requested roots.")
    return bundles, units


def _batch_command(unit: HeaderUnit) -> str:
    flags = " ".join(MSVC_FLAGS)
    return (
        f'cl.exe /nologo {flags} /I"{unit.bundle}" /c '
        f'"%ROOT%translation-units\\{unit.key}.cpp" '
        f'/Fo"%ROOT%objects\\{unit.key}.obj" '
        f'>"%ROOT%diagnostics\\{unit.key}.log" 2>&1'
    )


def write_validation_script(
    validation_directory: Path, developer_command_file: Path, units: list[HeaderUnit]
) -> Path:
    """Write a continuing batch script with per-unit result markers."""
    script = validation_directory / "validate_headers.cmd"
    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        'set "ROOT=%~dp0"',
        'if not exist "%ROOT%objects" mkdir "%ROOT%objects"',
        'if not exist "%ROOT%diagnostics" mkdir "%ROOT%diagnostics"',
        f'call "{developer_command_file}" -arch=x64',
        "if errorlevel 1 exit /b 9001",
        'set "EXIT_CODE=0"',
    ]
    for unit in units:
        lines.extend(
            [
                f"echo DDON_HEADER_START^|{unit.key}^|{unit.header.name}",
                _batch_command(unit),
                'set "UNIT_EXIT=!ERRORLEVEL!"',
                f"echo DDON_HEADER_RESULT^|{unit.key}^|!UNIT_EXIT!",
                'if not "!UNIT_EXIT!"=="0" set "EXIT_CODE=1"',
            ]
        )
    lines.extend(["endlocal & exit /b %EXIT_CODE%", ""])
    validation_directory.mkdir(parents=True, exist_ok=True)
    script.write_text("\r\n".join(lines), encoding="utf-8", newline="")
    return script


def _diagnostic_codes(text: str) -> list[str]:
    return sorted({match.upper() for match in DIAGNOSTIC_CODE.findall(text)})


def _diagnostic_excerpt(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if DIAGNOSTIC_CODE.search(line)]
    return lines[:20]


def _classify_failure(codes: list[str]) -> str:
    if not codes:
        return "compile_error"
    if UNRESOLVED_CODES.intersection(codes):
        return "unresolved_identifier_or_type"
    return "syntax_or_compile_error"


def _read_result_markers(output: str) -> dict[str, int]:
    results: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 3 and parts[0] == "DDON_HEADER_RESULT":
            try:
                results[parts[1]] = int(parts[2])
            except ValueError:
                continue
    return results


def _unit_result(
    unit: HeaderUnit, exit_code: int | None, process_timed_out: bool
) -> dict[str, Any]:
    log_text = (
        unit.diagnostic_log.read_text(encoding="utf-8", errors="replace")
        if unit.diagnostic_log.is_file()
        else ""
    )
    codes = _diagnostic_codes(log_text)
    if process_timed_out and exit_code is None:
        status = "timed_out"
        failure_class = "incomplete"
    elif exit_code is None:
        status = "not_observed"
        failure_class = "incomplete"
    elif exit_code == 0:
        status = "passed"
        failure_class = "none"
    else:
        status = "failed"
        failure_class = _classify_failure(codes)
    return {
        "key": unit.key,
        "bundle": str(unit.bundle),
        "header": str(unit.header),
        "header_sha256": unit.header_sha256,
        "header_bytes": unit.header_bytes,
        "translation_unit": str(unit.translation_unit),
        "diagnostic_log": str(unit.diagnostic_log),
        "compiler_exit_code": exit_code,
        "status": status,
        "failure_class": failure_class,
        "diagnostic_codes": codes,
        "diagnostic_excerpt": _diagnostic_excerpt(log_text),
    }


def _run_script(script: Path, timeout_seconds: int) -> tuple[int | None, str, bool]:
    execution = run_command(
        ["cmd.exe", "/d", "/c", "call", str(script)], timeout_seconds=timeout_seconds
    )
    return execution.returncode, execution.output, execution.timed_out


def run_validation(
    input_roots: list[Path], validation_directory: Path, timeout_seconds: int
) -> dict[str, Any]:
    """Prepare and execute the complete per-header MSVC validation."""
    started = _utc_now()
    validation_directory = validation_directory.expanduser().resolve()
    validation_directory.mkdir(parents=True, exist_ok=True)
    bundles, units = discover_units(input_roots, validation_directory)
    developer_command_file = get_visual_studio_developer_command_file()
    compiler = test_msvc_toolchain(developer_command_file)
    script = write_validation_script(validation_directory, developer_command_file, units)
    process_exit_code, output, timed_out = _run_script(script, timeout_seconds)
    markers = _read_result_markers(output)
    results = [_unit_result(unit, markers.get(unit.key), timed_out) for unit in units]
    counts = validation_counts(results)
    failure_classes: dict[str, int] = {}
    diagnostic_codes: dict[str, int] = {}
    for result in results:
        failure_class = str(result["failure_class"])
        failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
        for code in result["diagnostic_codes"]:
            diagnostic_codes[str(code)] = diagnostic_codes.get(str(code), 0) + 1
    report = {
        "schema_version": 1,
        "tool": "tools.sonar.validate_header_bundle",
        "validation_scope": "season2_header_closures",
        "started_at": started,
        "finished_at": _utc_now(),
        "compiler_path": compiler,
        "msvc_flags": list(MSVC_FLAGS),
        "input_roots": [str(path.expanduser().resolve()) for path in input_roots],
        "validation_directory": str(validation_directory),
        "validation_script": str(script),
        "bundle_count": len(bundles),
        "header_count": len(units),
        "header_file_count": len(units),
        "msvc_unit_count": len(units),
        "process_exit_code": process_exit_code,
        "process_timed_out": timed_out,
        "counts": counts.to_dict(),
        "status": "observed" if counts.complete and not timed_out else "partial",
        "failure_classes": failure_classes,
        "diagnostic_code_counts": dict(sorted(diagnostic_codes.items())),
        "units": results,
    }
    write_json_atomic(validation_directory / "msvc-header-validation.json", report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        action="append",
        required=True,
        help="Season batch root, symbol bundle, or ps4 header directory; repeatable.",
    )
    parser.add_argument("--validation-directory", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_validation(args.input_root, args.validation_directory, args.timeout_seconds)
    except (HeaderValidationError, SonarAnalysisError, OSError) as error:
        print(f"MSVC header validation failed to run: {error}", file=sys.stderr)
        return 1
    summary = {
        key: report[key]
        for key in (
            "compiler_path",
            "bundle_count",
            "header_count",
            "process_exit_code",
            "process_timed_out",
            "counts",
            "failure_classes",
            "diagnostic_code_counts",
        )
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report["counts"].get("passed", 0) == report["header_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

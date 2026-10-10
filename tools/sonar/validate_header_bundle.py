"""Compile every generated header closure individually with MSVC on Windows."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_COMPILER_METADATA_BYTES = 64 * 1024

if __package__ in {None, ""}:
    # Keep the established ``python tools/sonar/validate_header_bundle.py``
    # launcher usable while retaining package-relative imports for normal use.
    _repository_root = Path(__file__).resolve().parents[2]
    if str(_repository_root) not in sys.path:
        sys.path.insert(0, str(_repository_root))
    from tools.sonar.msvc_validation.catalog import build_header_catalog
    from tools.sonar.msvc_validation.commands import run_command
    from tools.sonar.msvc_validation.manifest_binding import (
        CompilerHeader,
        inspect_manifest_binding,
    )
    from tools.sonar.msvc_validation.publication import write_json_atomic
    from tools.sonar.msvc_validation.reports import aggregate_unit_metrics, validation_counts
    from tools.sonar.msvc_validation.validation_cli import explain_main, parse_args
    from tools.sonar.prepare_msvc_analysis import (
        SonarAnalysisError,
        get_visual_studio_developer_command_file,
        test_msvc_toolchain,
    )
else:
    from .msvc_validation.catalog import build_header_catalog
    from .msvc_validation.commands import run_command
    from .msvc_validation.manifest_binding import CompilerHeader, inspect_manifest_binding
    from .msvc_validation.publication import write_json_atomic
    from .msvc_validation.reports import aggregate_unit_metrics, validation_counts
    from .msvc_validation.validation_cli import explain_main, parse_args
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

    @property
    def stdout_log(self) -> Path:
        return self.diagnostic_log.with_name(f"{self.diagnostic_log.stem}.stdout.log")

    @property
    def stderr_log(self) -> Path:
        return self.diagnostic_log.with_name(f"{self.diagnostic_log.stem}.stderr.log")


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
    ps4_bundles = sorted(
        (path for path in root.rglob("ps4") if path.is_dir() and any(path.glob("*.h"))),
        key=lambda path: str(path).lower(),
    )
    if ps4_bundles:
        return ps4_bundles
    header_bundles = sorted(
        {path.parent for path in root.rglob("*.h")},
        key=lambda path: str(path).lower(),
    )
    if not header_bundles:
        raise HeaderValidationError(f"No generated header bundles were found below '{root}'.")
    return header_bundles


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
    used_translation_names: set[str] = set()
    for sequence, entry in enumerate(catalog.entries, start=1):
        bundle = entry.bundle
        translation_name = _translation_unit_name(entry.header, sequence, used_translation_names)
        used_translation_names.add(translation_name.lower())
        unit = HeaderUnit(
            sequence=sequence,
            bundle=bundle,
            header=entry.header,
            translation_unit=validation_directory / "translation-units" / translation_name,
            object_file=validation_directory
            / "objects"
            / Path(translation_name).with_suffix(".obj"),
            diagnostic_log=validation_directory
            / "diagnostics"
            / Path(translation_name).with_suffix(".log"),
            header_sha256=entry.sha256,
            header_bytes=entry.byte_count,
        )
        _write_unit(unit)
        units.append(unit)
    if not units:
        raise HeaderValidationError("No generated headers were found in the requested roots.")
    return bundles, units


def _translation_unit_name(header: Path, sequence: int, used: set[str]) -> str:
    """Use the established tutorial name while keeping duplicate bundles collision-safe."""
    candidate = (
        "compile_tutorial.cpp"
        if header.name == "rTutorialDialogMessage.h"
        else f"u{sequence:05d}.cpp"
    )
    return candidate if candidate.lower() not in used else f"u{sequence:05d}.cpp"


def _batch_command(unit: HeaderUnit) -> str:
    flags = " ".join(MSVC_FLAGS)
    return (
        f'cl.exe /nologo {flags} /I"{unit.bundle}" /c '
        f'"%ROOT%translation-units\\{unit.translation_unit.name}" '
        f'/Fo"%ROOT%objects\\{unit.object_file.name}" '
        f'>"%ROOT%diagnostics\\{unit.stdout_log.name}" '
        f'2>"%ROOT%diagnostics\\{unit.stderr_log.name}"'
    )


def _write_aggregate_source(validation_directory: Path, units: list[HeaderUnit]) -> Path:
    path = validation_directory / "translation-units" / "compile_all.cpp"
    includes = [f'#include "{str(unit.header).replace(chr(92), "/")}"' for unit in units]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// Generated aggregate acceptance translation unit.\n" + "\n".join(includes) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def write_validation_script(
    validation_directory: Path, developer_command_file: Path, units: list[HeaderUnit]
) -> Path:
    """Write a continuing batch script with per-unit result markers."""
    script = validation_directory / "validate_headers.cmd"
    aggregate_source = _write_aggregate_source(validation_directory, units)
    aggregate_object = validation_directory / "objects" / "compile_all.obj"
    aggregate_stdout = validation_directory / "diagnostics" / "compile_all.stdout.log"
    aggregate_stderr = validation_directory / "diagnostics" / "compile_all.stderr.log"
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
    unique_bundles = sorted({unit.bundle for unit in units}, key=lambda path: str(path).lower())
    include_paths = " ".join(f'/I"{bundle}"' for bundle in unique_bundles)
    if len(include_paths) > 2048:
        aggregate_rsp = validation_directory / "translation-units" / "compile_all.rsp"
        aggregate_rsp.parent.mkdir(parents=True, exist_ok=True)
        aggregate_rsp.write_text(
            "\n".join(f'/I"{bundle}"' for bundle in unique_bundles) + "\n",
            encoding="utf-8",
        )
        include_cmd = f'@"%ROOT%translation-units\\{aggregate_rsp.name}"'
    else:
        include_cmd = include_paths
    lines.extend(
        [
            "echo DDON_AGGREGATE_START^|compile_all.cpp",
            f"cl.exe /nologo {' '.join(MSVC_FLAGS)} {include_cmd} /c "
            f'"%ROOT%translation-units\\{aggregate_source.name}" '
            f'/Fo"%ROOT%objects\\{aggregate_object.name}" '
            f'>"%ROOT%diagnostics\\{aggregate_stdout.name}" '
            f'2>"%ROOT%diagnostics\\{aggregate_stderr.name}"',
            'set "AGGREGATE_EXIT=!ERRORLEVEL!"',
            "echo DDON_AGGREGATE_RESULT^|compile_all.cpp^|!AGGREGATE_EXIT!",
            'if not "!AGGREGATE_EXIT!"=="0" set "EXIT_CODE=1"',
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


def _read_aggregate_marker(output: str) -> int | None:
    for line in output.splitlines():
        parts = line.strip().split("|")
        if (
            len(parts) == 3
            and parts[0] == "DDON_AGGREGATE_RESULT"
            and parts[1] == "compile_all.cpp"
        ):
            try:
                return int(parts[2])
            except ValueError:
                return None
    return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _object_status(path: Path, exit_code: int | None) -> str:
    if exit_code is None:
        return "not_observed"
    return "present" if path.is_file() else "missing"


def _unit_result(
    unit: HeaderUnit, exit_code: int | None, process_timed_out: bool
) -> dict[str, Any]:
    stdout = _read_text(unit.stdout_log)
    stderr = _read_text(unit.stderr_log)
    log_text = stdout + stderr
    codes = _diagnostic_codes(log_text)
    object_status = _object_status(unit.object_file, exit_code)
    if process_timed_out and exit_code is None:
        status = "timed_out"
        failure_class = "incomplete"
    elif exit_code is None:
        status = "not_observed"
        failure_class = "incomplete"
    elif exit_code == 0 and object_status == "present":
        status = "passed"
        failure_class = "none"
    elif exit_code == 0:
        status = "failed"
        failure_class = "object_missing"
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
        "stdout_log": str(unit.stdout_log),
        "stderr_log": str(unit.stderr_log),
        "stdout_sha256": _sha256_text(stdout),
        "stderr_sha256": _sha256_text(stderr),
        "compiler_exit_code": exit_code,
        "object_file": str(unit.object_file),
        "object_status": object_status,
        "status": status,
        "failure_class": failure_class,
        "diagnostic_codes": codes,
        "diagnostic_excerpt": _diagnostic_excerpt(log_text),
    }


def _aggregate_result(
    validation_directory: Path, exit_code: int | None, process_timed_out: bool
) -> dict[str, Any]:
    object_file = validation_directory / "objects" / "compile_all.obj"
    stdout_log = validation_directory / "diagnostics" / "compile_all.stdout.log"
    stderr_log = validation_directory / "diagnostics" / "compile_all.stderr.log"
    stdout = _read_text(stdout_log)
    stderr = _read_text(stderr_log)
    object_status = _object_status(object_file, exit_code)
    if process_timed_out and exit_code is None:
        status, failure_class = "timed_out", "incomplete"
    elif exit_code is None:
        status, failure_class = "not_observed", "incomplete"
    elif exit_code == 0 and object_status == "present":
        status, failure_class = "passed", "none"
    elif exit_code == 0:
        status, failure_class = "failed", "object_missing"
    else:
        codes = _diagnostic_codes(stdout + stderr)
        status, failure_class = "failed", _classify_failure(codes)
    return {
        "translation_unit": "compile_all.cpp",
        "source": str(validation_directory / "translation-units" / "compile_all.cpp"),
        "object_file": str(object_file),
        "object_status": object_status,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
        "stdout_sha256": _sha256_text(stdout),
        "stderr_sha256": _sha256_text(stderr),
        "compiler_exit_code": exit_code,
        "status": status,
        "failure_class": failure_class,
        "diagnostic_codes": _diagnostic_codes(stdout + stderr),
        "diagnostic_excerpt": _diagnostic_excerpt(stdout + stderr),
    }


def _compiler_metadata(compiler: str) -> dict[str, object]:
    path = Path(compiler)
    metadata: dict[str, object] = {
        "compiler_path": compiler,
        "compiler_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        if path.is_file()
        else None,
        "compiler_version": None,
        "compiler_version_status": "not_observed",
    }
    if not path.is_file():
        return metadata
    try:
        result = run_command(
            [str(path), "/Bv"],
            timeout_seconds=30,
            max_output_bytes=MAX_COMPILER_METADATA_BYTES,
        )
    except OSError:
        return metadata
    if (
        result.timed_out
        or result.returncode is None
        or result.stdout_truncated
        or result.stderr_truncated
    ):
        return metadata
    output = result.output
    metadata["compiler_version_status"] = "observed" if output else "not_observed"
    metadata["compiler_version"] = output.strip()[:512] if output.strip() else None
    metadata["compiler_version_output_sha256"] = _sha256_text(output)
    return metadata


def _run_script(script: Path, timeout_seconds: int) -> tuple[int | None, str, bool]:
    execution = run_command(
        ["cmd.exe", "/d", "/c", "call", str(script)], timeout_seconds=timeout_seconds
    )
    if execution.stdout_truncated or execution.stderr_truncated:
        raise SonarAnalysisError(
            "MSVC validation command output was truncated; result markers are incomplete."
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
    publication = inspect_manifest_binding(
        (CompilerHeader(unit.header, unit.header_sha256, unit.header_bytes) for unit in units),
        input_roots,
    )
    developer_command_file = get_visual_studio_developer_command_file()
    compiler = test_msvc_toolchain(developer_command_file)
    compiler_metadata = _compiler_metadata(compiler)
    script = write_validation_script(validation_directory, developer_command_file, units)
    process_exit_code, output, timed_out = _run_script(script, timeout_seconds)
    markers = _read_result_markers(output)
    results = [_unit_result(unit, markers.get(unit.key), timed_out) for unit in units]
    aggregate = _aggregate_result(validation_directory, _read_aggregate_marker(output), timed_out)
    counts = validation_counts(results)
    (
        failure_classes,
        diagnostic_codes,
        raw_diagnostic_counts,
        unique_location_counts,
        error_limit_unit_count,
    ) = aggregate_unit_metrics(results)
    is_observed = counts.complete and not timed_out
    report = {
        "schema_version": 2,
        "tool": "tools.sonar.validate_header_bundle",
        "validation_scope": "season2_header_closures",
        "publication": publication,
        "started_at": started,
        "finished_at": _utc_now(),
        **compiler_metadata,
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
        "standalone_status": "observed" if is_observed else "partial",
        "aggregate_status": aggregate["status"],
        "status": (
            "observed"
            if is_observed
            and aggregate["status"] == "passed"
            and publication["status"] == "matched"
            else "partial"
        ),
        "failure_classes": failure_classes,
        "diagnostic_code_counts": dict(sorted(diagnostic_codes.items())),
        "raw_diagnostic_counts": dict(sorted(raw_diagnostic_counts.items())),
        "unique_location_counts": unique_location_counts,
        "error_limit_unit_count": error_limit_unit_count,
        "aggregate": aggregate,
        "units": results,
    }
    write_json_atomic(validation_directory / "msvc-header-validation.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.explain_report is not None:
        return explain_main(args)
    if not args.input_root or args.explain_unit or args.requirement_witness:
        print("Normal validation requires --input-root and no --explain-unit", file=sys.stderr)
        return 2
    try:
        report = run_validation(args.input_root, args.validation_directory, args.timeout_seconds)
    except (HeaderValidationError, SonarAnalysisError, OSError) as error:
        print(f"MSVC header validation failed to run: {error}", file=sys.stderr)
        return 1
    summary = {
        key: report[key]
        for key in (
            "compiler_path",
            "compiler_version",
            "bundle_count",
            "header_count",
            "process_exit_code",
            "process_timed_out",
            "counts",
            "standalone_status",
            "aggregate_status",
            "publication",
            "failure_classes",
            "diagnostic_code_counts",
            "raw_diagnostic_counts",
            "unique_location_counts",
            "error_limit_unit_count",
        )
        if key in report
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

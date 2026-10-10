"""Recompile one manifest-bound failed header for bounded diagnostic evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..prepare_msvc_analysis import (
    get_visual_studio_developer_command_file,
    test_msvc_toolchain,
)
from .commands import CommandExecution, run_command
from .publication import write_json_atomic

REFERENCE_COMMIT = "1ef40e3d656c6e77e07ead58308e76b7b55ebf4a"
PROBE_FLAGS = (
    "/std:c++latest",
    "/EHsc",
    "/W4",
    "/Zc:__cplusplus",
    "/diagnostics:caret",
    "/FC",
    "/showIncludes",
    "/sourceDependencies",
)
_ERROR = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s+(?:fatal )?error (?P<code>C\d{4}):\s*(?P<message>.*)$",
    re.MULTILINE,
)
_INCLUDE = re.compile(r"^Note: including file:(?P<indent>\s+)(?P<path>\S.*)$")
MAX_INCLUDE_RECORDS = 512
MAX_DEPENDENCY_BYTES = 2 * 1024 * 1024
REQUIREMENT_KINDS = frozenset(
    {
        "alias_declaration",
        "enclosing_owner",
        "template_primary",
        "complete_definition",
        "declaration",
    }
)


class FailureProbeError(RuntimeError):
    """The selected probe cannot be bound to a complete published input."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_report(path: Path, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("units"), list):
        raise FailureProbeError("Selected validation report has no unit list")
    matches = [unit for unit in report["units"] if unit.get("key") == key]
    if len(matches) != 1 or matches[0].get("status") != "failed":
        raise FailureProbeError("Select exactly one failed header unit")
    if report.get("publication", {}).get("status") != "matched":
        raise FailureProbeError("Selected report lacks matched publication evidence")
    if not _acceptance_flags_match(report):
        raise FailureProbeError("Selected report uses a different MSVC acceptance profile")
    if not _all_units_attempted(report["units"]):
        raise FailureProbeError("Selected report has unattempted or timed-out headers")
    return report, matches[0]


def _acceptance_flags_match(report: dict[str, Any]) -> bool:
    return report.get("msvc_flags") == list(PROBE_FLAGS[:4])


def _all_units_attempted(units: list[dict[str, Any]]) -> bool:
    return all(unit.get("status") in {"passed", "failed"} for unit in units)


def _verify_publication(report: dict[str, Any]) -> dict[str, Any]:
    for unit in report["units"]:
        header = Path(unit["header"])
        if not header.is_file() or _sha256(header) != unit["header_sha256"]:
            raise FailureProbeError(f"Published header changed or disappeared: {header}")
    source: dict[str, Any] | None = None
    for record in report["publication"]["manifests"]:
        path = Path(record["path"])
        if not path.is_file() or _sha256(path) != record["sha256"]:
            raise FailureProbeError(f"Publication manifest changed or disappeared: {path}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if source is None:
            source = manifest.get("source")
        elif source != manifest.get("source"):
            raise FailureProbeError("Selected bundle has conflicting source identities")
    return source or {}


def _reference_identity(root: Path) -> dict[str, str]:
    chapter = root / "n4950" / "class.md"
    if not chapter.is_file():
        raise FailureProbeError(f"Missing cppstdmd n4950 reference at {root}")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or commit != REFERENCE_COMMIT:
        raise FailureProbeError("cppstdmd checkout is not at the pinned reference commit")
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if dirty.returncode != 0 or dirty.stdout.strip():
        raise FailureProbeError("cppstdmd checkout has local changes or cannot be inspected")
    return {"path": str(root), "commit": commit, "draft": "n4950"}


def _declaration_requirement(path: Path | None, source: dict[str, Any]) -> dict[str, Any]:
    if path is None:
        return {
            "status": "unclassified",
            "reason": "Compiler diagnostics alone do not establish a source-bound declaration requirement",
        }
    witness = json.loads(path.read_text(encoding="utf-8"))
    _validate_requirement_witness(witness, source)
    _validate_source_evidence(witness, source)
    return {**witness, "status": "source_bound_witness", "path": str(path), "sha256": _sha256(path)}


def _validate_requirement_witness(witness: object, source: dict[str, Any]) -> None:
    if not isinstance(witness, dict) or witness.get("source_sha256") != source.get("sha256"):
        raise FailureProbeError("Requirement witness has no matching source SHA-256")
    if witness.get("kind") not in REQUIREMENT_KINDS:
        raise FailureProbeError("Requirement witness has an unsupported declaration kind")
    if not isinstance(witness.get("entity"), str) or not witness["entity"]:
        raise FailureProbeError("Requirement witness has no entity")
    for field in ("cu_offset", "die_offset"):
        value = witness.get(field)
        if not _valid_offset(value):
            raise FailureProbeError(f"Requirement witness has no valid {field}")
    if not isinstance(witness.get("rule"), str) or not witness["rule"]:
        raise FailureProbeError("Requirement witness has no standard clause label")


def _valid_offset(value: object) -> bool:
    return type(value) is int and value >= 0


def _validate_source_evidence(witness: dict[str, Any], source: dict[str, Any]) -> None:
    evidence = Path(witness.get("evidence_path", ""))
    if not evidence.is_file() or _sha256(evidence) != witness.get("evidence_sha256"):
        raise FailureProbeError("Requirement witness has no matching source evidence artifact")
    data = json.loads(evidence.read_text(encoding="utf-8"))
    if data.get("source_sha256") != source.get("sha256"):
        raise FailureProbeError("Requirement evidence has a different source identity")
    for observation in data.get("observations", []):
        if observation.get("cu") != witness["cu_offset"]:
            continue
        if _observation_matches(observation, witness):
            return
    raise FailureProbeError("Requirement DIE/CU is absent from source evidence")


def _observation_matches(observation: dict[str, Any], witness: dict[str, Any]) -> bool:
    entity = witness["entity"]
    name = observation.get("name") or ""
    if observation.get("die") == witness["die_offset"]:
        return name.endswith(f"::{entity}") or name == entity
    owner, _, child_name = entity.rpartition("::")
    if not owner or not name.endswith(f"::{owner}"):
        return False
    return any(
        child.get("die") == witness["die_offset"] and child.get("name") == child_name
        for child in observation.get("children", [])
    )


def _first_error(output: str) -> dict[str, Any] | None:
    match = _ERROR.search(output)
    if match is None:
        return None
    return {
        "path": match["path"],
        "line": int(match["line"]),
        "column": int(match["column"]) if match["column"] else None,
        "code": match["code"],
        "message": match["message"].strip(),
        "classification": "first_reported_error_not_proven_root_cause",
    }


def _include_evidence(output: str, error_path: str | None) -> dict[str, Any]:
    stack: list[tuple[int, str]] = []
    records: list[dict[str, Any]] = []
    target = _normalized_path(error_path)
    chain: list[str] = []
    truncated = False
    for line in output.splitlines():
        match = _INCLUDE.match(line)
        if match is None:
            continue
        if len(records) >= MAX_INCLUDE_RECORDS:
            truncated = True
            break
        depth = len(match["indent"])
        path = match["path"].strip()
        stack = [entry for entry in stack if entry[0] < depth]
        stack.append((depth, path))
        records.append({"depth": depth, "path": path})
        if target and _normalized_path(path) == target and not chain:
            chain = [item for _, item in stack]
    return {"records": records, "first_error_chain": chain, "truncated": truncated}


def _normalized_path(path: str | None) -> str | None:
    return str(Path(path).resolve()).casefold() if path else None


def _source_dependencies(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "not_emitted", "path": str(path)}
    if path.stat().st_size > MAX_DEPENDENCY_BYTES:
        return {"status": "too_large", "path": str(path), "sha256": _sha256(path)}
    content = path.read_bytes()
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except UnicodeError, json.JSONDecodeError:
        return {"status": "invalid", "path": str(path), "sha256": _sha256(path)}
    payload = data.get("Data") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        return {"status": "invalid", "path": str(path), "sha256": _sha256(path)}
    includes = payload.get("Includes")
    if not isinstance(includes, list) or not all(isinstance(item, str) for item in includes):
        return {"status": "invalid", "path": str(path), "sha256": _sha256(path)}
    return {
        "status": "observed",
        "path": str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "source": payload.get("Source"),
        "include_count": len(includes),
        "includes": includes[:MAX_INCLUDE_RECORDS],
        "truncated": len(includes) > MAX_INCLUDE_RECORDS,
    }


def _write_probe_script(path: Path, developer: Path, header: Path, bundle: Path) -> Path:
    source = path / "selected.cpp"
    source.write_text(f'#include "{header.as_posix()}"\n', encoding="utf-8", newline="\n")
    script = path / "explain_selected.cmd"
    flags = " ".join(PROBE_FLAGS)
    script.write_text(
        "\r\n".join(
            [
                "@echo off",
                f'call "{developer}" -arch=x64',
                "if errorlevel 1 exit /b 9001",
                f'cl.exe /nologo {flags} "{path / "includes.json"}" '
                f'/I"{bundle}" /c "{source}" /Fo"{path / "selected.obj"}"',
                "",
            ]
        ),
        encoding="utf-8",
        newline="",
    )
    return script


def _probe_complete(
    execution: CommandExecution,
    first_error: dict[str, Any] | None,
    source_dependencies: dict[str, Any],
    include_trace: dict[str, Any],
    compiler_matches: bool,
) -> bool:
    return (
        not execution.timed_out
        and not execution.stdout_truncated
        and not execution.stderr_truncated
        and execution.returncode not in {None, 0}
        and first_error is not None
        and source_dependencies["status"] == "observed"
        and not source_dependencies["truncated"]
        and not include_trace["truncated"]
        and bool(include_trace["first_error_chain"])
        and compiler_matches
    )


def explain_failed_unit(
    report_path: Path,
    key: str,
    output_dir: Path,
    reference_root: Path,
    timeout_seconds: int = 120,
    requirement_witness: Path | None = None,
) -> dict[str, Any]:
    """Produce one optional probe without changing the acceptance report."""
    if timeout_seconds < 1:
        raise FailureProbeError("Probe timeout must be positive")
    report_path = report_path.resolve()
    report, unit = _read_report(report_path, key)
    source_identity = _verify_publication(report)
    reference = _reference_identity(reference_root.resolve())
    requirement = _declaration_requirement(requirement_witness, source_identity)
    header = Path(unit["header"]).resolve()
    bundle = Path(unit["bundle"]).resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    developer = get_visual_studio_developer_command_file()
    compiler = Path(test_msvc_toolchain(developer)).resolve()
    compiler_sha256 = _sha256(compiler)
    version = run_command([str(compiler), "/Bv"], timeout_seconds=30)
    if version.timed_out or version.stdout_truncated or version.stderr_truncated:
        raise FailureProbeError("MSVC version observation is incomplete")
    script = _write_probe_script(output_dir, developer, header, bundle)
    execution = run_command(
        ["cmd.exe", "/d", "/c", "call", str(script)], timeout_seconds=timeout_seconds
    )
    (output_dir / "stdout.log").write_text(execution.stdout, encoding="utf-8")
    (output_dir / "stderr.log").write_text(execution.stderr, encoding="utf-8")
    first_error = _first_error(execution.output)
    include_trace = _include_evidence(
        execution.output, first_error["path"] if first_error else None
    )
    source_dependencies = _source_dependencies(output_dir / "includes.json")
    complete = _probe_complete(
        execution,
        first_error,
        source_dependencies,
        include_trace,
        compiler_sha256 == report.get("compiler_sha256"),
    )
    result = {
        "schema_version": 1,
        "tool_sha256": _sha256(Path(__file__)),
        "status": "observed" if complete else "partial",
        "report": {"path": str(report_path), "sha256": _sha256(report_path)},
        "publication": report["publication"],
        "source_identity": source_identity,
        "unit_key": key,
        "header": str(header),
        "header_sha256": unit["header_sha256"],
        "reference": reference,
        "compiler": {
            "path": str(compiler),
            "sha256": compiler_sha256,
            "version": version.output.strip()[:512],
            "target": "x64-windows-msvc",
            "matches_acceptance_binary": compiler_sha256 == report.get("compiler_sha256"),
        },
        "flags": list(PROBE_FLAGS),
        "script": str(script),
        "exit_code": execution.returncode,
        "timed_out": execution.timed_out,
        "output_truncated": execution.stdout_truncated or execution.stderr_truncated,
        "first_error": first_error,
        "include_trace": include_trace,
        "source_dependencies": source_dependencies,
        "declaration_requirement": requirement,
    }
    write_json_atomic(output_dir / "selected-failure.json", result)
    return result

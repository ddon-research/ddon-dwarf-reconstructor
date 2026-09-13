"""Opt-in, bounded llvm-mca analysis for marked compiler assembly."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ...core.content_hash import sha256_file
from ...domain.models.performance import AssemblyAnalysisEvidence, EvidenceStatus
from ..toolchain_process import ToolchainExportError, run_bounded_command

_BEGIN = re.compile(r"^\s*#\s*LLVM-MCA-BEGIN(?:\s+(?P<name>\S.*?))?\s*$")
_END = re.compile(r"^\s*#\s*LLVM-MCA-END\s*$")
_MAX_INPUT_BYTES = 64 * 1024 * 1024
_MAX_OUTPUT_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _AnalysisContext:
    assembly: Path
    tool: Path
    output_dir: Path
    regions: tuple[str, ...]
    input_sha: str
    tool_sha: str
    version: str
    command: tuple[str, ...]
    output_path: Path
    manifest_path: Path


def analyze_assembly(
    assembly: Path,
    tool: Path,
    output_dir: Path,
    *,
    json_output: bool = True,
    show_encoding: bool = False,
    timeline: bool = False,
    resource_pressure: bool = False,
    timeout_seconds: float = 300.0,
) -> AssemblyAnalysisEvidence:
    """Analyze only a post-compile assembly file containing valid MCA regions."""
    context = _prepare_analysis(
        assembly,
        tool,
        output_dir,
        json_output=json_output,
        show_encoding=show_encoding,
        timeline=timeline,
        resource_pressure=resource_pressure,
        timeout_seconds=timeout_seconds,
    )
    context.output_dir.mkdir(parents=True, exist_ok=True)
    staging = context.output_dir / f".{context.output_path.name}.staging-{uuid4().hex}"
    staging.mkdir()
    staged_output = staging / context.output_path.name
    try:
        return _execute_analysis(context, staged_output, timeout_seconds)
    finally:
        _remove_directory(staging)


def _prepare_analysis(
    assembly: Path,
    tool: Path,
    output_dir: Path,
    *,
    json_output: bool,
    show_encoding: bool,
    timeline: bool,
    resource_pressure: bool,
    timeout_seconds: float,
) -> _AnalysisContext:
    assembly = assembly.resolve()
    tool = tool.resolve()
    output_dir = output_dir.resolve()
    if not assembly.is_file():
        raise ValueError(f"Assembly input does not exist: {assembly}")
    if not tool.is_file():
        raise ValueError(f"llvm-mca executable does not exist: {tool}")
    regions = _regions(assembly)
    input_sha = sha256_file(assembly)
    tool_sha = sha256_file(tool)
    version = _tool_version(tool, timeout_seconds)
    arguments = _arguments(
        assembly,
        json_output=json_output,
        show_encoding=show_encoding,
        timeline=timeline,
        resource_pressure=resource_pressure,
    )
    command = (str(tool), *arguments)
    output_name = f"llvm-mca-{input_sha[:16]}-{tool_sha[:16]}.{'json' if json_output else 'txt'}"
    return _AnalysisContext(
        assembly,
        tool,
        output_dir,
        regions,
        input_sha,
        tool_sha,
        version,
        command,
        output_dir / output_name,
        output_dir / f"{output_name}.manifest.json",
    )


def _execute_analysis(
    context: _AnalysisContext, staged_output: Path, timeout_seconds: float
) -> AssemblyAnalysisEvidence:
    try:
        result = run_bounded_command(
            context.tool,
            context.command[1:],
            staged_output,
            timeout_seconds,
            max_output_bytes=_MAX_OUTPUT_BYTES,
        )
        if result.stdout_truncated:
            return _failed_context(
                context, EvidenceStatus.FAILED, "llvm-mca output exceeded the bounded cap"
            )
        if result.returncode != 0:
            return _failed_context(
                context,
                EvidenceStatus.FAILED,
                f"llvm-mca returned {result.returncode}: {result.stderr_preview}",
            )
        staged_output.replace(context.output_path)
        evidence = AssemblyAnalysisEvidence(
            input_path=context.assembly,
            input_sha256=context.input_sha,
            tool=context.tool,
            tool_sha256=context.tool_sha,
            tool_version=context.version,
            command=context.command,
            status=EvidenceStatus.OBSERVED,
            output_path=context.output_path,
            output_sha256=sha256_file(context.output_path),
            manifest_path=context.manifest_path,
            regions=context.regions,
        )
        _write_manifest(context.manifest_path, evidence)
        return evidence
    except TimeoutError as error:
        return _failed_context(context, EvidenceStatus.BLOCKED, str(error))
    except (OSError, ToolchainExportError) as error:
        return _failed_context(context, EvidenceStatus.UNAVAILABLE, type(error).__name__)


def _failed_context(
    context: _AnalysisContext, status: EvidenceStatus, diagnostic: str
) -> AssemblyAnalysisEvidence:
    return _failed(
        context.assembly,
        context.tool,
        context.input_sha,
        context.tool_sha,
        context.version,
        context.command,
        context.regions,
        status,
        diagnostic,
    )


def _regions(path: Path) -> tuple[str, ...]:
    size = path.stat().st_size
    if size > _MAX_INPUT_BYTES:
        raise ValueError(f"Assembly input exceeds {_MAX_INPUT_BYTES} bytes")
    text = path.read_text(encoding="utf-8", errors="replace")
    active: str | None = None
    names: list[str] = []
    for line in text.splitlines():
        active = _advance_region(line, active, names)
    if active is not None:
        raise ValueError(f"llvm-mca region was not closed: {active}")
    if not names:
        raise ValueError("llvm-mca requires at least one LLVM-MCA-BEGIN/END region")
    return tuple(names)


def _advance_region(line: str, active: str | None, names: list[str]) -> str | None:
    begin = _BEGIN.match(line)
    if begin is not None:
        if active is not None:
            raise ValueError("llvm-mca regions may not overlap")
        name = (begin.group("name") or "region").strip()
        if name in names:
            raise ValueError(f"duplicate llvm-mca region: {name}")
        names.append(name)
        return name
    if _END.match(line):
        if active is None:
            raise ValueError("llvm-mca region ended without a begin marker")
        return None
    return active


def _arguments(
    assembly: Path,
    *,
    json_output: bool,
    show_encoding: bool,
    timeline: bool,
    resource_pressure: bool,
) -> tuple[str, ...]:
    values = ["--json"] if json_output else []
    if show_encoding:
        values.append("--show-encoding")
    if timeline:
        values.append("--timeline")
    if resource_pressure:
        values.append("--resource-pressure")
    values.append(str(assembly))
    return tuple(values)


def _failed(
    assembly: Path,
    tool: Path,
    input_sha: str,
    tool_sha: str,
    version: str,
    command: tuple[str, ...],
    regions: tuple[str, ...],
    status: EvidenceStatus,
    diagnostic: str,
) -> AssemblyAnalysisEvidence:
    return AssemblyAnalysisEvidence(
        input_path=assembly,
        input_sha256=input_sha,
        tool=tool,
        tool_sha256=tool_sha,
        tool_version=version,
        command=command,
        status=status,
        regions=regions,
        diagnostics=(diagnostic,),
    )


def _write_manifest(path: Path, evidence: AssemblyAnalysisEvidence) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(evidence.to_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _tool_version(path: Path, timeout_seconds: float) -> str:
    try:
        result = subprocess.run(
            (str(path), "--version"),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return "unavailable"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0][:512] if output else "unavailable"


def _remove_directory(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_directory(child)
        else:
            child.unlink(missing_ok=True)
    path.rmdir()


__all__ = ["analyze_assembly"]

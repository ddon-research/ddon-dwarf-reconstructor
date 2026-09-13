"""Canonical assembly replay and bounded Orbis toolchain evidence."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..core.content_hash import sha256_file, sha256_text
from ..domain.models.disassembly import OrbisInstruction
from ..domain.models.implementation_validation import (
    CompilerEvidence,
    SemanticParity,
    ValidationStatus,
)
from ..domain.services.cpp_reconstruction.control_flow import compare_static_edges
from .implementation_assembler import assemble_canonical_source
from .implementation_assembly_source import canonical_assembly_source
from .implementation_assembly_source import instruction_bytes as _instruction_bytes
from .implementation_assembly_source import safe_name as _safe_name
from .implementation_linker import link_object as _link_object
from .implementation_object_metadata import collect_object_metadata
from .orbis_objdump_parsing import parse_instructions
from .toolchain_process import (
    BoundedCaptureResult,
    ToolchainExportError,
    ToolIdentityCache,
    run_bounded_capture,
)
from .toolchain_process import timeout_metadata as _timeout_metadata


def emit_and_assemble_method(
    method_id: str,
    instructions: tuple[OrbisInstruction, ...],
    output_dir: Path,
    assembler: Path | None,
    *,
    effect_status: ValidationStatus,
    readelf: Path | None = None,
    objdump: Path | None = None,
    linker: Path | None = None,
    assembly_ready: bool = True,
    timeout_seconds: float | None = None,
    assembly_profile: str = "byte-replay",
    expected_start: int | None = None,
    expected_size: int | None = None,
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    """Write canonical byte assembly and optionally accept the resulting object."""
    if not assembly_ready:
        return _not_ready_evidence(
            effect_status, "assembly gate is incomplete; no target artifact was emitted"
        )
    if not instructions:
        return _not_ready_evidence(
            effect_status, "method has no decoded instructions; no target artifact was emitted"
        )
    return _emit_ready_method(
        method_id,
        instructions,
        output_dir,
        assembler,
        effect_status,
        readelf,
        objdump,
        linker,
        timeout_seconds,
        assembly_profile,
        (expected_start, expected_size),
    )


def _not_ready_evidence(
    effect_status: ValidationStatus, diagnostic: str
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    return (
        CompilerEvidence(
            status=ValidationStatus.NOT_OBSERVED,
            profile="orbis-as",
            diagnostics=(diagnostic,),
        ),
        SemanticParity(
            status=ValidationStatus.NOT_OBSERVED,
            effect_status=effect_status,
            diagnostics=(diagnostic,),
        ),
        (),
    )


def _emit_ready_method(
    method_id: str,
    instructions: tuple[OrbisInstruction, ...],
    output_dir: Path,
    assembler: Path | None,
    effect_status: ValidationStatus,
    readelf: Path | None,
    objdump: Path | None,
    linker: Path | None,
    timeout_seconds: float | None,
    assembly_profile: str,
    expected_range: tuple[int | None, int | None],
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = _safe_name(method_id)
    assembly_path = output_dir / f"{safe_id}.s"
    object_path = output_dir / f"{safe_id}.o"
    raw_bytes, diagnostics = _instruction_bytes(
        instructions,
        expected_start=expected_range[0],
        expected_size=expected_range[1],
    )
    if raw_bytes is None:
        compiler = CompilerEvidence(
            status=ValidationStatus.FAILED,
            profile="orbis-as",
            diagnostics=tuple(diagnostics),
        )
        return compiler, _unobserved_parity(effect_status, diagnostics), ()
    assembly_source, assembly_diagnostics = canonical_assembly_source(
        method_id,
        instructions,
        assembly_profile=assembly_profile,
        expected_start=expected_range[0],
        expected_size=expected_range[1],
    )
    if assembly_source is None:
        compiler = CompilerEvidence(
            status=ValidationStatus.FAILED,
            profile="orbis-as",
            assembly_profile=assembly_profile,
            diagnostics=assembly_diagnostics,
        )
        return compiler, _unobserved_parity(effect_status, assembly_diagnostics), ()
    assert assembly_source is not None
    assembly_path.write_text(assembly_source, encoding="utf-8", newline="\n")
    artifacts = [str(assembly_path)]
    preflight = _assembly_preflight(assembler, effect_status, artifacts)
    if preflight is not None:
        return preflight
    assert assembler is not None
    return _assemble_and_finish_method(
        assembler,
        readelf,
        objdump,
        linker,
        output_dir,
        safe_id,
        assembly_path,
        object_path,
        raw_bytes,
        instructions,
        effect_status,
        artifacts,
        timeout_seconds,
        assembly_profile,
    )


def _assemble_and_finish_method(
    assembler: Path,
    readelf: Path | None,
    objdump: Path | None,
    linker: Path | None,
    output_dir: Path,
    safe_id: str,
    assembly_path: Path,
    object_path: Path,
    raw_bytes: bytes,
    instructions: tuple[OrbisInstruction, ...],
    effect_status: ValidationStatus,
    artifacts: list[str],
    timeout_seconds: float | None,
    assembly_profile: str,
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    identity_cache = ToolIdentityCache()
    command = (str(assembler), "-o", str(object_path), str(assembly_path))
    compiler = _run_assembler(
        command,
        assembler,
        object_path,
        readelf=readelf,
        timeout_seconds=timeout_seconds,
        identity_cache=identity_cache,
    )
    compiler = replace(compiler, assembly_profile=assembly_profile)
    return _finish_assembled_method(
        compiler,
        object_path,
        raw_bytes,
        instructions,
        effect_status,
        objdump,
        linker,
        output_dir,
        safe_id,
        artifacts,
        timeout_seconds,
        assembly_profile,
        identity_cache,
    )


def _assembly_preflight(
    assembler: Path | None,
    effect_status: ValidationStatus,
    artifacts: list[str],
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]] | None:
    if assembler is None:
        compiler = CompilerEvidence(
            status=ValidationStatus.NOT_OBSERVED,
            diagnostics=("Orbis assembler was not supplied",),
        )
        return compiler, _unobserved_parity(effect_status), tuple(artifacts)
    if not assembler.exists():
        compiler = CompilerEvidence(
            status=ValidationStatus.UNAVAILABLE,
            tool=str(assembler),
            diagnostics=("Orbis assembler path does not exist",),
        )
        return compiler, _unobserved_parity(effect_status), tuple(artifacts)
    return None


def _unobserved_parity(
    effect_status: ValidationStatus, diagnostics: tuple[str, ...] | list[str] = ()
) -> SemanticParity:
    return _parity(
        effect_status,
        ValidationStatus.NOT_OBSERVED,
        ValidationStatus.NOT_OBSERVED,
        ValidationStatus.NOT_OBSERVED,
        diagnostics,
    )


def _finish_assembled_method(
    compiler: CompilerEvidence,
    object_path: Path,
    raw_bytes: bytes,
    instructions: tuple[OrbisInstruction, ...],
    effect_status: ValidationStatus,
    objdump: Path | None,
    linker: Path | None,
    output_dir: Path,
    safe_id: str,
    artifacts: list[str],
    timeout_seconds: float | None,
    assembly_profile: str,
    identity_cache: ToolIdentityCache | None = None,
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    if compiler.output_path is not None:
        artifacts.append(compiler.output_path)
    link_metadata, link_artifact, link_diagnostics = _link_object(
        object_path,
        linker,
        output_dir,
        safe_id,
        compiler.status,
        timeout_seconds=timeout_seconds,
        identity_cache=identity_cache,
    )
    if link_metadata:
        compiler = replace(
            compiler,
            object_metadata={**compiler.object_metadata, **link_metadata},
            diagnostics=tuple(compiler.diagnostics) + tuple(link_diagnostics),
        )
    if link_artifact is not None:
        artifacts.append(str(link_artifact))
    generated, objdump_metadata, objdump_diagnostics = _disassemble_object(
        object_path,
        objdump,
        output_dir,
        safe_id,
        timeout_seconds=timeout_seconds,
        identity_cache=identity_cache,
    )
    if objdump_metadata:
        compiler = replace(
            compiler,
            object_metadata={**compiler.object_metadata, **objdump_metadata},
            diagnostics=tuple(compiler.diagnostics) + tuple(objdump_diagnostics),
        )
    profile_status, profile_diagnostics = _validate_assembly_profile(
        compiler, safe_id, assembly_profile
    )
    if profile_status is not None:
        compiler = replace(
            compiler,
            status=profile_status,
            diagnostics=tuple(compiler.diagnostics) + tuple(profile_diagnostics),
        )
    section_name = ".text" if assembly_profile == "byte-replay" else f".text.{safe_id}"
    byte_status, byte_diagnostics = _compare_text_bytes(
        object_path, raw_bytes, section_name=section_name
    )
    cfg_status, external_status, edge_diagnostics = _edge_parity(instructions, generated, objdump)
    parity = _parity(
        effect_status,
        byte_status,
        cfg_status,
        external_status,
        (*profile_diagnostics, *byte_diagnostics, *objdump_diagnostics, *edge_diagnostics),
    )
    return compiler, parity, tuple(artifacts)


def _validate_assembly_profile(
    compiler: CompilerEvidence, safe_id: str, assembly_profile: str
) -> tuple[ValidationStatus | None, tuple[str, ...]]:
    if assembly_profile != "sectioned" or compiler.status is not ValidationStatus.OBSERVED:
        return None, ()
    metadata = compiler.object_metadata
    enabled = metadata.get("function_data_sections_enabled")
    sections = metadata.get("text_subsections")
    expected = f".text.{safe_id}"
    diagnostics: list[str] = []
    if enabled is not True:
        diagnostics.append("EF_FFUNC_DATA_SECS_ENABLED was not observed in the object")
    if not isinstance(sections, (tuple, list)) or expected not in sections:
        diagnostics.append(f"sectioned assembly did not publish {expected}")
    if diagnostics:
        return ValidationStatus.FAILED, tuple(diagnostics)
    return ValidationStatus.OBSERVED, ()


def _edge_parity(
    source: tuple[OrbisInstruction, ...],
    generated: tuple[OrbisInstruction, ...],
    objdump: Path | None,
) -> tuple[ValidationStatus, ValidationStatus, tuple[str, ...]]:
    if objdump is None:
        return (
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            ("Orbis objdump was not supplied; static edge parity is not observed",),
        )
    if not generated:
        return (
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            ("generated target object produced no decoded instructions",),
        )
    return compare_static_edges(source, generated)


def _disassemble_object(
    object_path: Path,
    objdump: Path | None,
    output_dir: Path,
    stem: str,
    *,
    timeout_seconds: float | None = None,
    identity_cache: ToolIdentityCache | None = None,
) -> tuple[tuple[OrbisInstruction, ...], dict[str, object], tuple[str, ...]]:
    if objdump is None:
        return (), {"objdump_status": ValidationStatus.NOT_OBSERVED.value}, ()
    if not objdump.exists():
        return (
            (),
            {
                "objdump_status": ValidationStatus.UNAVAILABLE.value,
                "objdump_tool": str(objdump),
            },
            ("Orbis objdump path does not exist",),
        )
    command = (str(objdump), "-d", "-C", str(object_path))
    identity = (identity_cache or ToolIdentityCache()).observe(
        objdump,
        timeout_seconds,
        profile="objdump",
    )
    metadata: dict[str, object] = {
        "objdump_tool": str(objdump),
        "objdump_tool_sha256": identity.sha256,
        "objdump_version": identity.version,
        "objdump_command": command,
    }
    completed, capture_diagnostics = _capture_objdump_output(
        command,
        objdump,
        metadata,
        timeout_seconds,
    )
    if completed is None:
        return (), metadata, capture_diagnostics
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status, status_diagnostics = _objdump_capture_status(completed)
    metadata.update(
        {
            "objdump_status": status.value,
            "objdump_stdout_sha256": sha256_text(stdout),
            "objdump_stderr_sha256": sha256_text(stderr),
        }
    )
    if status_diagnostics:
        return (), metadata, status_diagnostics
    instructions = parse_instructions(stdout)
    if not instructions:
        return (), metadata, ("Orbis objdump returned no decoded target instructions",)
    return instructions, metadata, ()


def _capture_objdump_output(
    command: tuple[str, ...],
    objdump: Path,
    metadata: dict[str, object],
    timeout_seconds: float | None,
) -> tuple[BoundedCaptureResult | None, tuple[str, ...]]:
    started = time.perf_counter()
    try:
        return run_bounded_capture(objdump, command[1:], timeout_seconds), ()
    except TimeoutError:
        metadata.update(
            {
                "objdump_status": ValidationStatus.BLOCKED.value,
                "timeout": _timeout_metadata(str(objdump), "objdump", started, timeout_seconds),
            }
        )
        return None, ("Orbis objdump execution timed out",)
    except (OSError, ToolchainExportError) as error:
        metadata["objdump_status"] = ValidationStatus.UNAVAILABLE.value
        return None, (f"Orbis objdump could not be executed: {type(error).__name__}",)


def _objdump_capture_status(
    completed: BoundedCaptureResult,
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if completed.stdout_truncated or completed.stderr_truncated:
        return ValidationStatus.FAILED, ("Orbis objdump output exceeded the bounded cap",)
    if completed.returncode != 0:
        return ValidationStatus.FAILED, ("Orbis objdump rejected the generated target object",)
    return ValidationStatus.OBSERVED, ()


def _run_assembler(
    command: tuple[str, ...],
    assembler: Path,
    object_path: Path,
    *,
    readelf: Path | None,
    timeout_seconds: float | None = None,
    identity_cache: ToolIdentityCache | None = None,
) -> CompilerEvidence:
    identity = (identity_cache or ToolIdentityCache()).observe(
        assembler,
        timeout_seconds,
        profile="assembler",
    )
    tool_hash = identity.sha256
    version = identity.version
    started = time.perf_counter()
    try:
        completed = run_bounded_capture(
            assembler,
            command[1:],
            timeout_seconds,
        )
    except TimeoutError:
        return _compiler_failure(
            assembler,
            command,
            tool_hash,
            version,
            ValidationStatus.BLOCKED,
            "Orbis assembler execution timed out",
            {"timeout": _timeout_metadata(str(assembler), "assembler", started, timeout_seconds)},
        )
    except (OSError, ToolchainExportError) as error:
        return _compiler_failure(
            assembler,
            command,
            tool_hash,
            version,
            ValidationStatus.UNAVAILABLE,
            f"Orbis assembler could not be executed: {type(error).__name__}",
        )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status, diagnostics = _assembler_capture_status(completed)
    return CompilerEvidence(
        status=status,
        tool=str(assembler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        output_path=str(object_path) if object_path.exists() else None,
        output_sha256=sha256_file(object_path) if object_path.exists() else None,
        object_metadata={
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            **collect_object_metadata(
                object_path,
                readelf,
                timeout_seconds=timeout_seconds,
                identity_cache=identity_cache,
            ),
        },
        diagnostics=diagnostics,
    )


def _compiler_failure(
    assembler: Path,
    command: tuple[str, ...],
    tool_hash: str | None,
    version: str | None,
    status: ValidationStatus,
    diagnostic: str,
    object_metadata: dict[str, object] | None = None,
) -> CompilerEvidence:
    return CompilerEvidence(
        status=status,
        tool=str(assembler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        object_metadata={} if object_metadata is None else object_metadata,
        diagnostics=(diagnostic,),
    )


def _assembler_capture_status(
    completed: BoundedCaptureResult,
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if completed.stdout_truncated or completed.stderr_truncated:
        return ValidationStatus.FAILED, ("Orbis assembler output exceeded the bounded cap",)
    if completed.returncode != 0:
        return ValidationStatus.FAILED, ("Orbis assembler rejected canonical assembly",)
    return ValidationStatus.OBSERVED, ()


def _compare_text_bytes(
    object_path: Path, expected: bytes, *, section_name: str = ".text"
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if not object_path.exists():
        return ValidationStatus.NOT_OBSERVED, ("assembler produced no object",)
    try:
        with object_path.open("rb") as stream:
            section = ELFFile(stream).get_section_by_name(section_name)
            actual = section.data() if section is not None else b""
    except (ELFError, OSError, ValueError) as error:
        return ValidationStatus.PARTIAL, (
            f"target object could not be parsed: {type(error).__name__}",
        )
    if actual == expected:
        return ValidationStatus.OBSERVED, ()
    return ValidationStatus.FAILED, (
        f"target {section_name} bytes differ: expected {len(expected)} bytes, observed {len(actual)}",
    )


def _parity(
    effect_status: ValidationStatus,
    byte_status: ValidationStatus,
    cfg_status: ValidationStatus,
    external_edge_status: ValidationStatus,
    diagnostics: tuple[str, ...] | list[str],
) -> SemanticParity:
    status = ValidationStatus.PARTIAL
    if byte_status is ValidationStatus.FAILED or effect_status is ValidationStatus.FAILED:
        status = ValidationStatus.FAILED
    elif all(
        status is ValidationStatus.OBSERVED
        for status in (byte_status, cfg_status, external_edge_status, effect_status)
    ):
        status = ValidationStatus.OBSERVED
    elif all(
        status is ValidationStatus.NOT_OBSERVED
        for status in (byte_status, cfg_status, external_edge_status, effect_status)
    ):
        status = ValidationStatus.NOT_OBSERVED
    return SemanticParity(
        status=status,
        byte_status=byte_status,
        cfg_status=cfg_status,
        external_edge_status=external_edge_status,
        effect_status=effect_status,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "assemble_canonical_source",
    "canonical_assembly_source",
    "collect_object_metadata",
    "emit_and_assemble_method",
]

"""Canonical assembly replay and bounded Orbis toolchain evidence."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.disassembly import OrbisInstruction
from ..domain.models.implementation_validation import (
    CompilerEvidence,
    SemanticParity,
    ValidationStatus,
)
from .implementation_linker import link_object as _link_object
from .implementation_object_metadata import collect_object_metadata
from .implementation_parity import compare_static_edges
from .orbis_objdump_parsing import OrbisObjdumpParsingMixin


def canonical_assembly_source(
    method_id: str,
    instructions: tuple[OrbisInstruction, ...],
) -> tuple[str | None, tuple[str, ...]]:
    """Return exact-byte GNU/Clang assembly for one observed method slice."""
    raw_bytes, diagnostics = _instruction_bytes(instructions)
    if raw_bytes is None:
        return None, tuple(diagnostics)
    safe_id = _safe_name(method_id)
    lines = [
        ".text",
        f".globl {safe_id}",
        f".type {safe_id}, @function",
        f"{safe_id}:",
    ]
    for offset in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[offset : offset + 16]
        lines.append("    .byte " + ", ".join(f"0x{value:02x}" for value in chunk))
    lines.extend([f".size {safe_id}, .-{safe_id}", ""])
    return "\n".join(lines), ()


def assemble_canonical_source(
    method_id: str,
    source: str,
    assembler: Path | None,
    *,
    timeout_seconds: float | None = None,
) -> tuple[bytes | None, tuple[str, ...]]:
    """Assemble canonical source and return only the accepted object bytes."""
    if assembler is None:
        return None, ("Orbis assembler was not supplied; object was not emitted",)
    if not assembler.is_file():
        return None, ("Orbis assembler path does not exist; object was not emitted",)
    safe_id = _safe_name(method_id)
    with tempfile.TemporaryDirectory(prefix="ddon-canonical-assembly-") as temporary:
        root = Path(temporary)
        assembly_path = root / f"{safe_id}.s"
        object_path = root / f"{safe_id}.o"
        assembly_path.write_text(source, encoding="utf-8", newline="\n")
        try:
            completed = subprocess.run(
                (str(assembler), "-o", str(object_path), str(assembly_path)),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, ("Orbis assembler execution timed out",)
        except OSError:
            return None, ("Orbis assembler could not be executed",)
        if completed.returncode != 0 or not object_path.is_file():
            return None, ("Orbis assembler rejected canonical assembly",)
        return object_path.read_bytes(), ()


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
) -> tuple[CompilerEvidence, SemanticParity, tuple[str, ...]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = _safe_name(method_id)
    assembly_path = output_dir / f"{safe_id}.s"
    object_path = output_dir / f"{safe_id}.o"
    raw_bytes, diagnostics = _instruction_bytes(instructions)
    if raw_bytes is None:
        compiler = CompilerEvidence(
            status=ValidationStatus.FAILED,
            profile="orbis-as",
            diagnostics=tuple(diagnostics),
        )
        return compiler, _unobserved_parity(effect_status, diagnostics), ()
    assembly_source, _ = canonical_assembly_source(method_id, instructions)
    assert assembly_source is not None
    assembly_path.write_text(assembly_source, encoding="utf-8", newline="\n")
    artifacts = [str(assembly_path)]
    preflight = _assembly_preflight(assembler, effect_status, artifacts)
    if preflight is not None:
        return preflight
    assert assembler is not None

    command = (str(assembler), "-o", str(object_path), str(assembly_path))
    compiler = _run_assembler(
        command,
        assembler,
        object_path,
        readelf=readelf,
        timeout_seconds=timeout_seconds,
    )
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
    )
    if objdump_metadata:
        compiler = replace(
            compiler,
            object_metadata={**compiler.object_metadata, **objdump_metadata},
            diagnostics=tuple(compiler.diagnostics) + tuple(objdump_diagnostics),
        )
    byte_status, byte_diagnostics = _compare_text_bytes(object_path, raw_bytes)
    cfg_status, external_status, edge_diagnostics = _edge_parity(instructions, generated, objdump)
    parity = _parity(
        effect_status,
        byte_status,
        cfg_status,
        external_status,
        (*byte_diagnostics, *objdump_diagnostics, *edge_diagnostics),
    )
    return compiler, parity, tuple(artifacts)


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
    metadata: dict[str, object] = {
        "objdump_tool": str(objdump),
        "objdump_tool_sha256": _sha256_file(objdump),
        "objdump_version": _tool_version(objdump, timeout_seconds),
        "objdump_command": command,
    }
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        metadata.update(
            {
                "objdump_status": ValidationStatus.BLOCKED.value,
                "timeout": _timeout_metadata(str(objdump), "objdump", started, timeout_seconds),
            }
        )
        return (), metadata, ("Orbis objdump execution timed out",)
    except OSError as error:
        metadata["objdump_status"] = ValidationStatus.UNAVAILABLE.value
        return (), metadata, (f"Orbis objdump could not be executed: {type(error).__name__}",)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    metadata.update(
        {
            "objdump_status": (
                ValidationStatus.OBSERVED.value
                if completed.returncode == 0
                else ValidationStatus.FAILED.value
            ),
            "objdump_stdout_sha256": _sha256_text(stdout),
            "objdump_stderr_sha256": _sha256_text(stderr),
        }
    )
    if completed.returncode != 0:
        return (), metadata, ("Orbis objdump rejected the generated target object",)
    instructions = OrbisObjdumpParsingMixin.parse_instructions(stdout)
    if not instructions:
        return (), metadata, ("Orbis objdump returned no decoded target instructions",)
    return instructions, metadata, ()


def _instruction_bytes(
    instructions: tuple[OrbisInstruction, ...],
) -> tuple[bytes | None, list[str]]:
    result = bytearray()
    diagnostics: list[str] = []
    for instruction in instructions:
        value = "".join(instruction.raw_bytes.split())
        if len(value) % 2 or not value:
            diagnostics.append(f"invalid raw bytes at 0x{instruction.address:x}")
            continue
        try:
            result.extend(bytes.fromhex(value))
        except ValueError:
            diagnostics.append(f"non-hex raw bytes at 0x{instruction.address:x}")
    return (None, diagnostics) if diagnostics else (bytes(result), diagnostics)


def _run_assembler(
    command: tuple[str, ...],
    assembler: Path,
    object_path: Path,
    *,
    readelf: Path | None,
    timeout_seconds: float | None = None,
) -> CompilerEvidence:
    tool_hash = _sha256_file(assembler)
    version = _tool_version(assembler, timeout_seconds)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CompilerEvidence(
            status=ValidationStatus.BLOCKED,
            tool=str(assembler),
            tool_sha256=tool_hash,
            version=version,
            command=command,
            object_metadata={
                "timeout": _timeout_metadata(str(assembler), "assembler", started, timeout_seconds)
            },
            diagnostics=("Orbis assembler execution timed out",),
        )
    except OSError as error:
        return CompilerEvidence(
            status=ValidationStatus.UNAVAILABLE,
            tool=str(assembler),
            tool_sha256=tool_hash,
            version=version,
            command=command,
            diagnostics=(f"Orbis assembler could not be executed: {type(error).__name__}",),
        )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status = ValidationStatus.OBSERVED if completed.returncode == 0 else ValidationStatus.FAILED
    diagnostics = (
        ()
        if status is ValidationStatus.OBSERVED
        else ("Orbis assembler rejected canonical assembly",)
    )
    return CompilerEvidence(
        status=status,
        tool=str(assembler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        output_path=str(object_path) if object_path.exists() else None,
        output_sha256=_sha256_file(object_path) if object_path.exists() else None,
        object_metadata={
            "stdout_sha256": _sha256_text(stdout),
            "stderr_sha256": _sha256_text(stderr),
            **collect_object_metadata(
                object_path,
                readelf,
                object_path.parent,
                object_path.stem,
                timeout_seconds=timeout_seconds,
            ),
        },
        diagnostics=diagnostics,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timeout_metadata(
    tool: str, stage: str, started: float, timeout_seconds: float | None
) -> dict[str, object]:
    return {
        "tool": tool,
        "stage": stage,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "configured_limit_seconds": timeout_seconds,
    }


def _compare_text_bytes(
    object_path: Path, expected: bytes
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if not object_path.exists():
        return ValidationStatus.NOT_OBSERVED, ("assembler produced no object",)
    try:
        with object_path.open("rb") as stream:
            section = ELFFile(stream).get_section_by_name(".text")
            actual = section.data() if section is not None else b""
    except (ELFError, OSError, ValueError) as error:
        return ValidationStatus.PARTIAL, (
            f"target object could not be parsed: {type(error).__name__}",
        )
    if actual == expected:
        return ValidationStatus.OBSERVED, ()
    return ValidationStatus.FAILED, (
        f"target .text bytes differ: expected {len(expected)} bytes, observed {len(actual)}",
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


def _tool_version(path: Path, timeout_seconds: float | None = None) -> str | None:
    try:
        completed = subprocess.run(
            (str(path), "--version"),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0][:512] if output else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    result = "".join(
        character if character.isalnum() or character in "._" else "_" for character in value
    )
    return result[:160] or "method"


__all__ = [
    "assemble_canonical_source",
    "canonical_assembly_source",
    "collect_object_metadata",
    "emit_and_assemble_method",
]

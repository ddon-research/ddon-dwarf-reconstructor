"""Reusable Orbis-clang ABI probes and compiler-generated assembly evidence."""

from __future__ import annotations

import time
from pathlib import Path

from ..core.content_hash import sha256_file, sha256_text
from ..domain.models.implementation_validation import (
    CompilerEvidence,
    ValidationStatus,
)
from .implementation_abi_probe_manifest import (
    aggregate_probe_status,
    build_probe_manifest,
    load_probe_manifest,
    write_probe_manifest,
)
from .implementation_object_metadata import collect_object_metadata
from .orbis_toolchain_contracts import SDK12_PROFILE_ID
from .toolchain_process import (
    ToolchainExportError,
    ToolIdentityCache,
    run_bounded_capture,
)

_TARGET_TRIPLE = "x86_64-scei-ps4"
_PROBES: tuple[tuple[str, str], ...] = (
    ("integer", 'extern "C" int probe_integer(int a, long b) { return a + (int)b; }\n'),
    ("floating", 'extern "C" double probe_floating(float a, double b) { return a + b; }\n'),
    (
        "aggregate",
        "struct ProbePair { long a; double b; };\n"
        'extern "C" ProbePair probe_aggregate(ProbePair value) { return value; }\n',
    ),
    (
        "this",
        "struct ProbeObject { int member(int value) const noexcept { return value + 1; } };\n",
    ),
    (
        "hidden_sret",
        "struct ProbeLarge { long a; long b; long c; };\n"
        'extern "C" ProbeLarge probe_hidden_sret(long value) { return {value, value, value}; }\n',
    ),
    ("variadic", 'extern "C" int probe_variadic(int count, ...) { return count; }\n'),
    (
        "virtual",
        "struct ProbeVirtual { virtual int value() const; };\n"
        "int ProbeVirtual::value() const { return 2; }\n",
    ),
    ("noexcept", 'extern "C" int probe_noexcept(int value) noexcept { return value; }\n'),
)


def run_abi_probe_matrix(
    compiler: Path | None,
    output_dir: Path,
    *,
    readelf: Path | None = None,
    timeout_seconds: float | None = None,
    toolchain_profile: str = SDK12_PROFILE_ID,
) -> tuple[CompilerEvidence, ...]:
    """Compile each ABI shape to post-optimization assembly and an object."""
    if compiler is None:
        return tuple(
            CompilerEvidence(
                status=ValidationStatus.NOT_OBSERVED,
                profile=f"abi:{name}",
                toolchain_profile=toolchain_profile,
                diagnostics=("Orbis clang++ was not supplied",),
            )
            for name, _source in _PROBES
        )
    if not compiler.exists():
        return tuple(
            CompilerEvidence(
                status=ValidationStatus.UNAVAILABLE,
                profile=f"abi:{name}",
                tool=str(compiler),
                toolchain_profile=toolchain_profile,
                diagnostics=("Orbis clang++ path does not exist",),
            )
            for name, _source in _PROBES
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    identity_cache = ToolIdentityCache()
    return tuple(
        _run_probe(
            name,
            source,
            compiler,
            output_dir,
            readelf,
            timeout_seconds=timeout_seconds,
            toolchain_profile=toolchain_profile,
            identity_cache=identity_cache,
        )
        for name, source in _PROBES
    )


def _run_probe(
    name: str,
    source: str,
    compiler: Path,
    output_dir: Path,
    readelf: Path | None,
    *,
    timeout_seconds: float | None,
    toolchain_profile: str,
    identity_cache: ToolIdentityCache,
) -> CompilerEvidence:
    source_path, assembly_path, object_path = _probe_paths(output_dir, name)
    source_path.write_text(source, encoding="utf-8", newline="\n")
    assembly_command, object_command = _probe_commands(
        compiler, source_path, assembly_path, object_path
    )
    identity = identity_cache.observe(compiler, timeout_seconds, profile="compiler-abi")
    tool_hash = identity.sha256 or sha256_file(compiler)
    version = identity.version
    assembly_result = _run(assembly_command, timeout_seconds)
    if assembly_result.status is not ValidationStatus.OBSERVED:
        return _failed_probe(
            name,
            compiler,
            tool_hash,
            version,
            object_command,
            assembly_result,
            toolchain_profile,
            source_path,
            assembly_path,
        )
    object_result = _run(object_command, timeout_seconds)
    if object_result.status is not ValidationStatus.OBSERVED:
        return _failed_probe(
            name,
            compiler,
            tool_hash,
            version,
            object_command,
            object_result,
            toolchain_profile,
            source_path,
            assembly_path,
        )
    metadata = _probe_metadata(
        assembly_result,
        object_result,
        assembly_command,
        object_command,
        assembly_path,
        object_path,
        readelf,
        output_dir,
        name,
        timeout_seconds,
        identity_cache,
    )
    return _successful_probe(
        name,
        compiler,
        tool_hash,
        version,
        object_command,
        source_path,
        assembly_path,
        object_path,
        toolchain_profile,
        metadata,
    )


def _probe_paths(output_dir: Path, name: str) -> tuple[Path, Path, Path]:
    return output_dir / f"{name}.cpp", output_dir / f"{name}.s", output_dir / f"{name}.o"


def _probe_commands(
    compiler: Path, source_path: Path, assembly_path: Path, object_path: Path
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    base = (
        str(compiler),
        "-target",
        _TARGET_TRIPLE,
        "-ffreestanding",
        "-fno-exceptions",
        "-fno-rtti",
        "-O2",
        "-g",
    )
    return (
        (*base, "-S", str(source_path), "-o", str(assembly_path)),
        (*base, "-c", str(source_path), "-o", str(object_path)),
    )


def _probe_metadata(
    assembly_result: _CommandResult,
    object_result: _CommandResult,
    assembly_command: tuple[str, ...],
    object_command: tuple[str, ...],
    assembly_path: Path,
    object_path: Path,
    readelf: Path | None,
    output_dir: Path,
    name: str,
    timeout_seconds: float | None,
    identity_cache: ToolIdentityCache,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "assembly_stdout_sha256": sha256_text(assembly_result.stdout),
        "assembly_stderr_sha256": sha256_text(assembly_result.stderr),
        "object_stdout_sha256": sha256_text(object_result.stdout),
        "object_stderr_sha256": sha256_text(object_result.stderr),
        "assembly_command": assembly_command,
        "object_command": object_command,
        "assembly": _assembly_metadata(assembly_path),
    }
    metadata.update(
        collect_object_metadata(
            object_path,
            readelf,
            timeout_seconds=timeout_seconds,
            identity_cache=identity_cache,
        )
    )
    return metadata


def _successful_probe(
    name: str,
    compiler: Path,
    tool_hash: str,
    version: str | None,
    command: tuple[str, ...],
    source_path: Path,
    assembly_path: Path,
    object_path: Path,
    toolchain_profile: str,
    metadata: dict[str, object],
) -> CompilerEvidence:
    return CompilerEvidence(
        status=ValidationStatus.OBSERVED,
        profile=f"abi:{name}",
        tool=str(compiler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        output_path=str(object_path),
        output_sha256=sha256_file(object_path),
        assembly_path=str(assembly_path),
        assembly_sha256=sha256_file(assembly_path),
        source_path=str(source_path),
        source_sha256=sha256_file(source_path),
        toolchain_profile=toolchain_profile,
        assembly_profile="compiler-generated",
        object_metadata=metadata,
        diagnostics=_default_diagnostics(metadata),
    )


def _failed_probe(
    name: str,
    compiler: Path,
    tool_hash: str,
    version: str | None,
    command: tuple[str, ...],
    result: _CommandResult,
    toolchain_profile: str,
    source_path: Path,
    assembly_path: Path,
) -> CompilerEvidence:
    return CompilerEvidence(
        status=result.status,
        profile=f"abi:{name}",
        tool=str(compiler),
        tool_sha256=tool_hash,
        version=version,
        command=command,
        assembly_path=str(assembly_path) if assembly_path.exists() else None,
        assembly_sha256=sha256_file(assembly_path) if assembly_path.exists() else None,
        source_path=str(source_path),
        source_sha256=sha256_file(source_path),
        toolchain_profile=toolchain_profile,
        assembly_profile="compiler-generated",
        object_metadata={
            "stdout_sha256": sha256_text(result.stdout),
            "stderr_sha256": sha256_text(result.stderr),
        },
        diagnostics=(f"ABI probe {name}: {result.diagnostic}",),
    )


class _CommandResult:
    def __init__(
        self,
        status: ValidationStatus,
        stdout: str = "",
        stderr: str = "",
        diagnostic: str = "",
    ) -> None:
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.diagnostic = diagnostic


def _run(command: tuple[str, ...], timeout_seconds: float | None) -> _CommandResult:
    started = time.perf_counter()
    try:
        completed = run_bounded_capture(
            Path(command[0]),
            command[1:],
            timeout_seconds,
        )
    except TimeoutError:
        return _CommandResult(
            ValidationStatus.BLOCKED,
            diagnostic=f"timed out after {time.perf_counter() - started:.3f}s",
        )
    except (OSError, ToolchainExportError) as error:
        return _CommandResult(ValidationStatus.UNAVAILABLE, diagnostic=type(error).__name__)
    if completed.stdout_truncated or completed.stderr_truncated:
        return _CommandResult(
            ValidationStatus.FAILED,
            completed.stdout,
            completed.stderr,
            "compiler output exceeded the bounded cap",
        )
    status = ValidationStatus.OBSERVED if completed.returncode == 0 else ValidationStatus.FAILED
    diagnostic = (
        "" if status is ValidationStatus.OBSERVED else f"compiler returned {completed.returncode}"
    )
    return _CommandResult(status, completed.stdout, completed.stderr, diagnostic)


def _assembly_metadata(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return {
            "status": ValidationStatus.UNAVAILABLE.value,
            "diagnostics": (type(error).__name__,),
        }
    sections = tuple(
        line.strip() for line in text.splitlines() if line.strip().startswith(".section")
    )
    has_debug_range_sections = any(
        marker in text
        for marker in (".debug_ranges", ".debug_rnglists", ".debug_loc", ".debug_loclists")
    )
    return {
        "status": ValidationStatus.OBSERVED.value,
        "sections": sections,
        "has_function_and_data_sections": ".function_and_data_sections" in text,
        "cfi_directive_count": sum(1 for line in text.splitlines() if ".cfi_" in line),
        "has_stack_size_section": ".sce_stack_sizes" in text,
        "has_debug_aranges": ".debug_aranges" in text,
        "has_debug_ranges": ".debug_ranges" in text,
        "has_debug_range_sections": has_debug_range_sections,
        "documented_defaults": {
            "att_syntax": ".intel_syntax" not in text,
            "function_sections": any(
                line.startswith(".section") and ".text." in line for line in sections
            ),
            "cfi": any(".cfi_" in line for line in text.splitlines()),
            "stack_metadata": ".sce_stack_sizes" in text,
            "debug_aranges": ".debug_aranges" in text,
        },
    }


def _default_diagnostics(metadata: dict[str, object]) -> tuple[str, ...]:
    assembly = metadata.get("assembly")
    if not isinstance(assembly, dict):
        return ("compiler-generated assembly defaults could not be inspected",)
    defaults = assembly.get("documented_defaults")
    if not isinstance(defaults, dict):
        return ("compiler-generated assembly defaults were not classified",)
    return tuple(
        f"documented compiler default was not observed: {name}"
        for name, observed in defaults.items()
        if observed is not True
    )


__all__ = [
    "aggregate_probe_status",
    "build_probe_manifest",
    "load_probe_manifest",
    "run_abi_probe_matrix",
    "write_probe_manifest",
]

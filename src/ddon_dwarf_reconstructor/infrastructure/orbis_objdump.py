"""Deterministic, bounded PS4 Orbis disassembly production.

The shipped PS4 ELF is not a generic host ELF.  This adapter invokes the
matching Orbis SDK objdump, converts its textual output into a versioned
machine-readable report, and retains that report in the durable artifact cache.
Human-formatted objdump output is never parsed at graph-query time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess as _subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from ..core.observability import get_logger, log_event
from ..domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisSdkDefinitionIdentity,
    OrbisToolIdentity,
    OrbisToolInvocation,
)
from ..domain.models.disassembly_scope import DisassemblyRequest, DisassemblyTarget
from .artifact_io import atomic_write_text
from .artifacts import SourceIdentityCatalog, get_artifact_cache_dir
from .orbis_objdump_parsing import (
    group_ranges,
    parse_instructions,
    parse_llvm_metadata,
    parse_llvm_unknown_dynamic_tags,
    parse_relocations,
    parse_symbols,
    select_root_symbols,
    select_target_symbols,
    slice_function_text,
)
from .orbis_objdump_profile_runtime import (
    OrbisProfileExecutor,
    ProfileResult,
)
from .orbis_objdump_profile_runtime import (
    _load_profile_cache as _load_cached_profile,
)
from .orbis_objdump_profiles import (
    DEBUG_FLAGS,
    DEFAULT_DWARF_MODES,
    DISASSEMBLY_FLAGS,
    DYNAMIC_RELOCATION_FLAGS,
    LLVM_METADATA_FLAGS,
    LLVM_TARGET_DISASSEMBLY_FLAGS,
    LLVM_TARGET_PROFILE,
    LLVM_TARGET_TRIPLE,
    PARSER_VERSION,
    PRIVATE_HEADERS_FLAGS,
    REPORT_SCHEMA_VERSION,
    SCE_METADATA_PARSER_VERSION,
    SOURCE_INTERMIXED_FLAGS,
    STANDARD_RELOCATION_FLAGS,
    SYMBOL_FLAGS,
)
from .orbis_report_factory import empty_disassembly_report
from .orbis_sdk_definitions import (
    SDK_DEFINITIONS_VERSION,
    sdk_definition_identity,
    sdk_definition_model,
)

# Normal implementation profiles are bounded by DWARF-derived function
# ranges, and the complete DWARF store is the authoritative debug-data source.
# Do not impose an arbitrary wall-clock cutoff on an SDK invocation.  Tests and
# explicitly constructed callers can still provide a positive timeout.
DEFAULT_TIMEOUT_SECONDS: float | None = None
logger = get_logger(__name__)
# Kept as a module-level compatibility seam for callers that patch the process runner.
subprocess = _subprocess

__all__ = [
    "OrbisFunctionDisassembly",
    "OrbisFunctionSymbol",
    "OrbisInstruction",
    "OrbisObjdumpProducer",
]


@dataclass(frozen=True, slots=True)
class _ProductionContext:
    """Validated, source-bound inputs for one disassembly report."""

    elf_path: Path
    root_symbol: str
    elf_sha256: str
    tool: OrbisToolIdentity
    artifact_key: str
    cache_path: Path
    dwarf_modes: tuple[str, ...]
    llvm_readobj_path: Path | None = None
    llvm_tool: OrbisToolIdentity | None = None
    llvm_objdump_path: Path | None = None
    llvm_objdump_tool: OrbisToolIdentity | None = None
    llvm_target_triple: str = LLVM_TARGET_TRIPLE
    sdk_definition_identity: OrbisSdkDefinitionIdentity | None = None
    scope_hash: str = ""
    scope_policy: str = "root-prefix-v1"
    target_count: int = 0
    targets: tuple[DisassemblyTarget, ...] = ()


class OrbisObjdumpProducer:
    """Run and cache bounded disassembly from the PS4 SDK toolchain."""

    def __init__(
        self,
        executable: Path,
        *,
        cache_root: Path | None = None,
        timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
        identity_catalog: SourceIdentityCatalog | None = None,
        llvm_readobj_path: Path | None = None,
        llvm_objdump_path: Path | None = None,
        llvm_target_triple: str = LLVM_TARGET_TRIPLE,
    ) -> None:
        self.executable = executable.resolve()
        self.cache_root = cache_root or get_artifact_cache_dir() / "orbis-objdump-v2"
        self.timeout_seconds = timeout_seconds
        self.identity_catalog = identity_catalog or SourceIdentityCatalog()
        self.llvm_readobj_path = llvm_readobj_path.resolve() if llvm_readobj_path else None
        self.llvm_objdump_path = llvm_objdump_path.resolve() if llvm_objdump_path else None
        self.llvm_target_triple = llvm_target_triple.strip() or LLVM_TARGET_TRIPLE
        self.last_cache_hit = False
        self._last_capture: tuple[str, str, int] | None = None
        self._dwarf_modes: tuple[str, ...] | None = None
        command_runner = None if type(self)._run is OrbisObjdumpProducer._run else self._run
        external_runner = (
            None
            if type(self)._run_with_executable is OrbisObjdumpProducer._run_with_executable
            else self._run_with_executable
        )
        self._profile_executor = OrbisProfileExecutor(
            self.executable,
            self.cache_root,
            self.timeout_seconds,
            command_runner=command_runner,
            external_runner=external_runner,
            capture_reader=lambda: self._last_capture,
        )

    def produce(self, elf_path: Path, request: DisassemblyRequest | str) -> OrbisDisassemblyReport:
        """Return bounded functions selected by a DWARF-derived request.

        A string remains accepted for knowledge-export and historical callers. It
        creates an explicitly marked root-prefix request and is never used by the
        implementation-discovery path.
        """
        normalized = DisassemblyRequest.root_only(request) if isinstance(request, str) else request
        context = self._build_context(elf_path, normalized)
        started_at = perf_counter()
        log_event(
            logger,
            logging.INFO,
            "orbis_disassembly_started",
            elf_path=context.elf_path,
            root_symbol=context.root_symbol,
            executable=self.executable,
            cache_path=context.cache_path,
        )
        cached = self._load_cached(context.cache_path, context.artifact_key)
        if cached is not None:
            self.last_cache_hit = True
            log_event(
                logger,
                logging.DEBUG,
                "orbis_disassembly_cache_hit",
                root_symbol=context.root_symbol,
                function_count=len(cached.functions),
                cache_path=context.cache_path,
            )
            return cached
        return self._produce_uncached(context, started_at)

    def _build_context(self, elf_path: Path, request: DisassemblyRequest) -> _ProductionContext:
        if not self.executable.is_file():
            raise ValueError(f"Orbis objdump executable not found: {self.executable}")
        if not elf_path.is_file():
            raise ValueError(f"ELF file not found: {elf_path}")
        elf_identity = self.identity_catalog.identify(elf_path)
        executable_identity = self.identity_catalog.identify(self.executable)
        version = self._read_version()
        target = self._read_target(elf_path)
        tool = OrbisToolIdentity(executable_identity.sha256, version, target)
        llvm_tool = self._llvm_tool_identity()
        llvm_objdump_tool = self._llvm_objdump_tool_identity()
        dwarf_modes = self._read_supported_dwarf_modes()
        artifact_key = self._artifact_key(
            elf_identity.sha256,
            tool,
            request.root_symbol,
            dwarf_modes,
            llvm_tool=llvm_tool,
            llvm_readobj_path=self.llvm_readobj_path,
            llvm_objdump_tool=llvm_objdump_tool,
            llvm_objdump_path=self.llvm_objdump_path,
            llvm_target_triple=self.llvm_target_triple,
            scope_hash=request.scope_hash,
            selection_policy=request.selection_policy,
        )
        cache_path = self.cache_root / artifact_key / "report.json"
        return _ProductionContext(
            elf_path=elf_path,
            root_symbol=request.root_symbol,
            elf_sha256=elf_identity.sha256,
            tool=tool,
            artifact_key=artifact_key,
            cache_path=cache_path,
            dwarf_modes=dwarf_modes,
            llvm_readobj_path=self.llvm_readobj_path,
            llvm_tool=llvm_tool,
            llvm_objdump_path=self.llvm_objdump_path,
            llvm_objdump_tool=llvm_objdump_tool,
            llvm_target_triple=self.llvm_target_triple,
            sdk_definition_identity=sdk_definition_model(),
            scope_hash=request.scope_hash,
            scope_policy=request.selection_policy,
            target_count=len(request.targets),
            targets=request.targets,
        )

    def _produce_uncached(
        self, context: _ProductionContext, started_at: float
    ) -> OrbisDisassemblyReport:
        from .orbis_objdump_workflow import produce_uncached

        return produce_uncached(self, context, started_at)

    # The three small adapters keep direct test seams and subclass fixtures
    # stable while production workflows use ``_profile_executor`` directly.
    def _executor(self) -> OrbisProfileExecutor:
        executor = getattr(self, "_profile_executor", None)
        if executor is None:
            executor = OrbisProfileExecutor(
                self.executable,
                getattr(self, "cache_root", Path(".orbis-objdump-cache")),
                getattr(self, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
                capture_reader=lambda: getattr(self, "_last_capture", None),
            )
            self._profile_executor = executor
        return executor

    def _run(self, arguments: list[str]) -> str:
        executor = self._executor()
        try:
            return executor.run_command(arguments)
        finally:
            self._last_capture = executor._last_capture

    def _run_with_executable(self, executable: Path, arguments: list[str]) -> str:
        executor = self._executor()
        try:
            return executor.run_with_executable(executable, arguments)
        finally:
            self._last_capture = executor._last_capture

    def _execute_profile(self, executable: Path, arguments: list[str]) -> ProfileResult:
        return self._executor().execute_profile(executable, arguments)

    def _shared_profile_dir(self, context: _ProductionContext) -> Path:
        return self._executor().shared_profile_dir(context)

    def _run_profile(self, *args: Any, **kwargs: Any) -> ProfileResult:
        return self._executor().run_profile(*args, **kwargs)

    # Direct function bindings retain the historical class-level parser API
    # without coupling the producer to a parser mixin.
    parse_symbols = staticmethod(parse_symbols)
    select_root_symbols = staticmethod(select_root_symbols)
    select_target_symbols = staticmethod(select_target_symbols)
    parse_instructions = staticmethod(parse_instructions)
    parse_relocations = staticmethod(parse_relocations)
    parse_llvm_metadata = staticmethod(parse_llvm_metadata)
    parse_llvm_unknown_dynamic_tags = staticmethod(parse_llvm_unknown_dynamic_tags)
    _group_ranges = staticmethod(group_ranges)

    @staticmethod
    def _load_profile_cache(
        metadata_path: Path,
        stdout_path: Path,
        stderr_path: Path,
        profile: str,
        arguments: list[str],
        tool: OrbisToolIdentity | None,
        executable: Path,
        *,
        cache_key: str | None = None,
        requested_triple: str | None = None,
        effective_triple: str | None = None,
        target_status: str | None = None,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> tuple[OrbisToolInvocation, ProfileResult] | None:
        """Retain the historical test/integration seam for profile-cache checks."""
        return _load_cached_profile(
            metadata_path,
            stdout_path,
            stderr_path,
            profile,
            arguments,
            tool,
            executable,
            cache_key=cache_key,
            requested_triple=requested_triple,
            effective_triple=effective_triple,
            target_status=target_status,
            range_start=range_start,
            range_end=range_end,
        )

    def _read_version(self) -> str:
        first_line = self._run(["--version"]).splitlines()
        if not first_line:
            raise ValueError("Orbis objdump returned no version information")
        version_lines = first_line[:2]
        return " | ".join(line.strip() for line in version_lines if line.strip())

    def _read_target(self, elf_path: Path) -> str:
        output = self._run(["-f", str(elf_path)])
        match = re.search(r"file format\s+(\S+)", output)
        if match is None:
            raise ValueError("Orbis objdump did not report an ELF target")
        return match.group(1)

    def _llvm_tool_identity(self) -> OrbisToolIdentity | None:
        return self._external_tool_identity(self.llvm_readobj_path, "generic-elf")

    def _llvm_objdump_tool_identity(self) -> OrbisToolIdentity | None:
        return self._external_tool_identity(self.llvm_objdump_path, "llvm-x86-64")

    def _external_tool_identity(
        self, executable: Path | None, target: str
    ) -> OrbisToolIdentity | None:
        if executable is None or not executable.is_file():
            return None
        identity = self.identity_catalog.identify(executable)
        try:
            output = self._run_with_executable(executable, ["--version"])
        except OSError, RuntimeError, TimeoutError:
            version = "unavailable"
        else:
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            version = " | ".join(lines[:2]) or "unknown"
        return OrbisToolIdentity(identity.sha256, version, target)

    def _read_supported_dwarf_modes(self) -> tuple[str, ...]:
        """Read modes from the local help surface, with a bounded fallback."""
        if self._dwarf_modes is not None:
            return self._dwarf_modes
        try:
            output = self._run(["--help"])
        except (OSError, RuntimeError, TimeoutError, AssertionError) as error:
            del error
            self._dwarf_modes = DEFAULT_DWARF_MODES
        else:
            dwarf_help = re.search(r"--dwarf\[(?P<modes>.*?)\]", output, flags=re.DOTALL)
            mode_text = dwarf_help.group("modes") if dwarf_help is not None else ""
            modes = tuple(dict.fromkeys(re.findall(r"=([A-Za-z][A-Za-z0-9_-]*)", mode_text)))
            self._dwarf_modes = modes or DEFAULT_DWARF_MODES
        return self._dwarf_modes

    @staticmethod
    def _raw_function_text(outputs: list[tuple[int, int, str]], symbol: OrbisFunctionSymbol) -> str:
        for start, stop, output in outputs:
            if start <= symbol.address < stop:
                return slice_function_text(output, symbol.address, symbol.end_address)
        return ""

    @staticmethod
    def _empty_report(
        context: _ProductionContext,
        invocations: list[OrbisToolInvocation],
        diagnostics: tuple[str, ...],
    ) -> OrbisDisassemblyReport:
        return empty_disassembly_report(context, invocations, diagnostics)

    @staticmethod
    def _artifact_key(
        elf_sha256: str,
        tool: OrbisToolIdentity,
        root_symbol: str,
        dwarf_modes: tuple[str, ...] = DEFAULT_DWARF_MODES,
        *,
        llvm_tool: OrbisToolIdentity | None = None,
        llvm_readobj_path: Path | None = None,
        llvm_objdump_tool: OrbisToolIdentity | None = None,
        llvm_objdump_path: Path | None = None,
        llvm_target_triple: str = LLVM_TARGET_TRIPLE,
        scope_hash: str | None = None,
        selection_policy: str = "root-prefix-v1",
    ) -> str:
        payload = {
            "elf_sha256": elf_sha256,
            "flags": DISASSEMBLY_FLAGS,
            "profile_flags": {
                "symbols": SYMBOL_FLAGS,
                "disassembly": DISASSEMBLY_FLAGS,
                "private_headers": PRIVATE_HEADERS_FLAGS,
                "standard_relocations": STANDARD_RELOCATION_FLAGS,
                "dynamic_relocations": DYNAMIC_RELOCATION_FLAGS,
                "llvm_metadata": LLVM_METADATA_FLAGS,
                LLVM_TARGET_PROFILE: LLVM_TARGET_DISASSEMBLY_FLAGS,
                "source_intermixed": SOURCE_INTERMIXED_FLAGS,
                "debug": DEBUG_FLAGS,
                "dwarf_modes": dwarf_modes,
            },
            "parser_version": PARSER_VERSION,
            "sce_metadata_parser_version": SCE_METADATA_PARSER_VERSION,
            "root_symbol": root_symbol,
            "scope_hash": scope_hash,
            "selection_policy": selection_policy,
            "schema_version": REPORT_SCHEMA_VERSION,
            "tool": asdict(tool),
            "llvm_tool": asdict(llvm_tool) if llvm_tool else None,
            "llvm_readobj_path": str(llvm_readobj_path or ""),
            "llvm_objdump_tool": asdict(llvm_objdump_tool) if llvm_objdump_tool else None,
            "llvm_objdump_path": str(llvm_objdump_path or ""),
            "llvm_target_triple": llvm_target_triple,
            "sdk_definitions_version": SDK_DEFINITIONS_VERSION,
            "sdk_definition_identity": sdk_definition_identity(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _load_cached(path: Path, artifact_key: str) -> OrbisDisassemblyReport | None:
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema_version") != REPORT_SCHEMA_VERSION:
                return None
            report_value = cast(dict[str, Any], value["report"])
            if report_value.get("artifact_key") != artifact_key:
                return None
            return OrbisDisassemblyReport.from_dict(report_value)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            log_event(
                logger,
                logging.WARNING,
                "orbis_disassembly_cache_invalid",
                cache_path=path,
                exc_info=error,
            )
            return None

    @staticmethod
    def _write_cached(path: Path, report: OrbisDisassemblyReport) -> None:
        atomic_write_text(
            path,
            json.dumps(
                {"schema_version": REPORT_SCHEMA_VERSION, "report": report.to_dict()},
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

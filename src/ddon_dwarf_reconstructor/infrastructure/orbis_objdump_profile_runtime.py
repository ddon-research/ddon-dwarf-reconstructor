"""Source-bound execution and caching for Orbis/LLVM evidence profiles."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, cast

from ..core.content_hash import sha256_text
from ..core.observability import get_logger, log_event
from ..domain.models.disassembly import OrbisToolIdentity, OrbisToolInvocation
from .artifact_io import atomic_write_text
from .orbis_objdump_profiles import PARSER_VERSION, SDK_DEFINITIONS_VERSION
from .orbis_sdk_definitions import sdk_definition_identity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileResult:
    """One profile's retained text and command outcome."""

    stdout: str
    stderr: str
    return_status: int | None
    status: str
    duration_ms: float
    diagnostics: tuple[str, ...] = ()


class ProfileCacheContext(Protocol):
    """Source/tool identity required by the shared profile cache boundary."""

    @property
    def elf_sha256(self) -> str: ...

    @property
    def tool(self) -> OrbisToolIdentity: ...

    @property
    def dwarf_modes(self) -> tuple[str, ...]: ...

    @property
    def llvm_readobj_path(self) -> Path | None: ...

    @property
    def llvm_tool(self) -> OrbisToolIdentity | None: ...

    @property
    def llvm_objdump_path(self) -> Path | None: ...

    @property
    def llvm_objdump_tool(self) -> OrbisToolIdentity | None: ...

    @property
    def llvm_target_triple(self) -> str: ...


class OrbisProfileExecutor:
    """Own command execution, source-bound cache validation, and retention."""

    def __init__(
        self,
        executable: Path,
        cache_root: Path,
        timeout_seconds: float | None,
        *,
        command_runner: Callable[[list[str]], str] | None = None,
        external_runner: Callable[[Path, list[str]], str] | None = None,
        capture_reader: Callable[[], tuple[str, str, int] | None] | None = None,
    ) -> None:
        self.executable = executable
        self.cache_root = cache_root
        self.timeout_seconds = timeout_seconds
        self._command_runner = command_runner
        self._external_runner = external_runner
        self._capture_reader = capture_reader
        self._last_capture: tuple[str, str, int] | None = None

    def run_profile(
        self,
        context: ProfileCacheContext,
        profile: str,
        arguments: list[str],
        invocations: list[OrbisToolInvocation],
        *,
        executable: Path | None = None,
        tool_identity: OrbisToolIdentity | None = None,
        requested_triple: str | None = None,
        effective_triple: str | None = None,
        target_status: str | None = None,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> ProfileResult:
        """Run or resume one source/tool/profile-bound command slice."""
        profile_executable = executable or self.executable
        profile_tool = tool_identity if tool_identity is not None else context.tool
        token = _profile_token(profile, arguments, profile_executable, profile_tool)
        profile_dir = self.shared_profile_dir(context)
        paths = _profile_paths(profile_dir, profile, token)
        cached = _load_profile_cache(
            *paths,
            profile,
            arguments,
            profile_tool,
            profile_executable,
            cache_key=token,
            requested_triple=requested_triple,
            effective_triple=effective_triple,
            target_status=target_status,
            range_start=range_start,
            range_end=range_end,
        )
        if cached is not None:
            invocations.append(cached[0])
            return cached[1]

        result = self.execute_profile(profile_executable, arguments)
        _write_text(paths[1], result.stdout)
        _write_text(paths[2], result.stderr)
        invocation = _invocation(
            profile,
            arguments,
            profile_executable,
            profile_tool,
            paths,
            result,
            cache_key=token,
            requested_triple=requested_triple,
            effective_triple=effective_triple,
            target_status=target_status,
            range_start=range_start,
            range_end=range_end,
        )
        _write_text(paths[0], json.dumps(asdict(invocation), indent=2, sort_keys=True) + "\n")
        invocations.append(invocation)
        return result

    def execute_profile(self, executable: Path, arguments: list[str]) -> ProfileResult:
        started_at = perf_counter()
        self._last_capture = None
        diagnostics: tuple[str, ...] = ()
        try:
            stdout = self._invoke(executable, arguments)
            capture = self._capture()
            stderr = capture[1] if capture is not None else ""
            return_status = capture[2] if capture is not None else 0
            status = "observed" if stdout else "empty"
        except (OSError, RuntimeError, TimeoutError, AssertionError) as error:
            timed_out = isinstance(error, TimeoutError)
            stdout = ""
            stderr = ""
            return_status = None
            status = "timeout" if timed_out else "unavailable"
            if status == "timeout":
                limit = (
                    f"{self.timeout_seconds:g}s"
                    if self.timeout_seconds is not None
                    else "configured"
                )
                diagnostics = (f"profile timed out (limit={limit})",)
            else:
                diagnostics = ("profile was unavailable",)
        return ProfileResult(
            stdout,
            stderr,
            return_status,
            status,
            round((perf_counter() - started_at) * 1000, 3),
            diagnostics,
        )

    def shared_profile_dir(self, context: ProfileCacheContext) -> Path:
        """Return a source/tool-bound directory shared by root-symbol reports."""
        identity = {
            "elf_sha256": context.elf_sha256,
            "tool": asdict(context.tool),
            "parser_version": PARSER_VERSION,
            "dwarf_modes": context.dwarf_modes,
            "llvm_readobj_path": str(context.llvm_readobj_path or ""),
            "llvm_tool": asdict(context.llvm_tool) if context.llvm_tool else None,
            "llvm_objdump_path": str(context.llvm_objdump_path or ""),
            "llvm_objdump_tool": (
                asdict(context.llvm_objdump_tool) if context.llvm_objdump_tool else None
            ),
            "llvm_target_triple": context.llvm_target_triple,
            "sdk_definitions_version": SDK_DEFINITIONS_VERSION,
            "sdk_definition_identity": sdk_definition_identity(),
        }
        token = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return self.cache_root / "profiles" / token

    def _invoke(self, executable: Path, arguments: list[str]) -> str:
        if executable == self.executable and self._command_runner is not None:
            return self._command_runner(arguments)
        if executable != self.executable and self._external_runner is not None:
            return self._external_runner(executable, arguments)
        return self.run_with_executable(executable, arguments)

    def _capture(self) -> tuple[str, str, int] | None:
        return self._capture_reader() if self._capture_reader is not None else self._last_capture

    def run_command(self, arguments: list[str]) -> str:
        return self.run_with_executable(self.executable, arguments)

    def run_with_executable(self, executable: Path, arguments: list[str]) -> str:
        command = [str(executable), *arguments]
        log_event(
            logger,
            logging.DEBUG,
            "orbis_objdump_invoked",
            executable=executable,
            argument_count=len(arguments),
            operation=arguments[0] if arguments else "",
        )
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            del error
            self._last_capture = ("", "", -1)
            log_event(
                logger,
                logging.WARNING,
                "orbis_objdump_timeout",
                configured_timeout_seconds=self.timeout_seconds,
                operation=arguments[0] if arguments else "",
            )
            timeout_label = (
                f"{self.timeout_seconds:g}s"
                if self.timeout_seconds is not None
                else "the configured limit"
            )
            raise TimeoutError(f"Orbis objdump timed out after {timeout_label}") from None
        self._last_capture = (result.stdout, result.stderr, result.returncode)
        if result.returncode != 0:
            log_event(
                logger,
                logging.WARNING,
                "orbis_objdump_failed",
                returncode=result.returncode,
                operation=arguments[0] if arguments else "",
            )
            raise RuntimeError(f"Orbis objdump failed ({result.returncode})")
        return result.stdout


def _profile_token(
    profile: str,
    arguments: list[str],
    executable: Path,
    tool: OrbisToolIdentity | None,
) -> str:
    payload = [profile, arguments, str(executable), asdict(tool) if tool is not None else None]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()[
        :20
    ]


def _profile_paths(profile_dir: Path, profile: str, token: str) -> tuple[Path, Path, Path]:
    stem = f"{_safe_profile_name(profile)}-{token}"
    return (
        profile_dir / f"{stem}.json",
        profile_dir / f"{stem}.stdout.txt",
        profile_dir / f"{stem}.stderr.txt",
    )


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
    """Load a profile only when its command, tool, and captured hashes agree."""
    if not all(path.is_file() for path in (metadata_path, stdout_path, stderr_path)):
        return None
    try:
        value = cast(dict[str, Any], json.loads(metadata_path.read_text(encoding="utf-8")))
        if not _profile_metadata_matches(
            value,
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
        ):
            return None
        stdout = stdout_path.read_text(encoding="utf-8")
        stderr = stderr_path.read_text(encoding="utf-8")
        if not _capture_hashes_match(value, stdout, stderr):
            return None
        invocation = _cached_invocation(
            value,
            profile,
            tool,
            stdout_path,
            stderr_path,
            cache_key=cache_key,
            requested_triple=requested_triple,
            effective_triple=effective_triple,
            target_status=target_status,
            range_start=range_start,
            range_end=range_end,
        )
        return invocation, ProfileResult(
            stdout,
            stderr,
            invocation.return_status,
            invocation.status,
            invocation.duration_ms or 0.0,
            invocation.diagnostics,
        )
    except OSError, KeyError, TypeError, ValueError, json.JSONDecodeError:
        return None


def _cached_invocation(
    value: dict[str, Any],
    profile: str,
    tool: OrbisToolIdentity | None,
    stdout_path: Path,
    stderr_path: Path,
    *,
    cache_key: str | None,
    requested_triple: str | None,
    effective_triple: str | None,
    target_status: str | None,
    range_start: int | None,
    range_end: int | None,
) -> OrbisToolInvocation:
    """Rehydrate invocation metadata after the captured text has been validated."""
    return OrbisToolInvocation(
        profile=profile,
        command=tuple(str(item) for item in value["command"]),
        flags=tuple(str(item) for item in value["flags"]),
        return_status=_optional_return_status(value.get("return_status")),
        status=str(value["status"]),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        stdout_sha256=str(value["stdout_sha256"]),
        stderr_sha256=str(value["stderr_sha256"]),
        tool_identity=tool,
        duration_ms=float(value["duration_ms"]),
        diagnostics=tuple(str(item) for item in value.get("diagnostics", [])),
        cache_key=str(value.get("cache_key")) if value.get("cache_key") else cache_key,
        requested_triple=_cached_string(value, "requested_triple", requested_triple),
        effective_triple=_cached_string(value, "effective_triple", effective_triple),
        target_status=_cached_string(value, "target_status", target_status),
        range_start=_optional_int(value.get("range_start"), range_start),
        range_end=_optional_int(value.get("range_end"), range_end),
    )


def _cached_string(value: dict[str, Any], name: str, fallback: str | None) -> str | None:
    cached = value.get(name)
    return str(cached) if cached is not None else fallback


def _profile_metadata_matches(
    value: dict[str, Any],
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
) -> bool:
    matches = all(
        (
            str(value.get("profile")) == profile,
            tuple(str(item) for item in value.get("command", ())) == (str(executable), *arguments),
            tuple(str(item) for item in value.get("flags", ())) == tuple(arguments),
            value.get("tool_identity") == (asdict(tool) if tool is not None else None),
        )
    )
    if not matches:
        return False
    optional_values = {
        "cache_key": cache_key,
        "requested_triple": requested_triple,
        "effective_triple": effective_triple,
        "target_status": target_status,
        "range_start": range_start,
        "range_end": range_end,
    }
    return all(
        expected is None or value.get(name) == expected
        for name, expected in optional_values.items()
    )


def _capture_hashes_match(value: dict[str, Any], stdout: str, stderr: str) -> bool:
    return value.get("stdout_sha256") == sha256_text(stdout) and value.get(
        "stderr_sha256"
    ) == sha256_text(stderr)


def _invocation(
    profile: str,
    arguments: list[str],
    executable: Path,
    tool: OrbisToolIdentity | None,
    paths: tuple[Path, Path, Path],
    result: ProfileResult,
    *,
    cache_key: str,
    requested_triple: str | None,
    effective_triple: str | None,
    target_status: str | None,
    range_start: int | None,
    range_end: int | None,
) -> OrbisToolInvocation:
    return OrbisToolInvocation(
        profile=profile,
        command=(str(executable), *arguments),
        flags=tuple(arguments),
        return_status=result.return_status,
        status=result.status,
        stdout_path=str(paths[1]),
        stderr_path=str(paths[2]),
        stdout_sha256=sha256_text(result.stdout),
        stderr_sha256=sha256_text(result.stderr),
        tool_identity=tool,
        duration_ms=result.duration_ms,
        diagnostics=result.diagnostics,
        cache_key=cache_key,
        requested_triple=requested_triple,
        effective_triple=effective_triple,
        target_status=target_status,
        range_start=range_start,
        range_end=range_end,
    )


def _write_text(path: Path, content: str) -> None:
    atomic_write_text(path, content)


def _safe_profile_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-") or "profile"


def _optional_return_status(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return int(value)
    raise TypeError(f"Expected integer return status, got {type(value).__name__}")


def _optional_int(value: object, fallback: int | None) -> int | None:
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"Expected integer range value, got {type(value).__name__}")
    return int(value)


__all__ = ["OrbisProfileExecutor", "ProfileResult"]

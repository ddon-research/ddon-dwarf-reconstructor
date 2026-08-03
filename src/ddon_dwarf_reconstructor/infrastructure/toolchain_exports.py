"""Bounded external-tool execution and source-bound export manifests."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from ..core.observability import get_logger, log_event
from ..domain.models.tool_evidence import (
    TOOL_EXPORT_SCHEMA_VERSION,
    ToolExport,
    ToolExportOutput,
    canonical_tool_export_key,
)
from ..domain.ports.source_identity import SourceIdentity
from .artifacts import SourceIdentityCatalog, sha256_file
from .toolchain_process import (
    BoundedCommandResult,
    ToolchainExportError,
)
from .toolchain_process import (
    read_text_prefix as _read_text_prefix,
)
from .toolchain_process import (
    run_bounded_command as _run_to_file,
)
from .toolchain_profiles import (
    ToolExportProfile,
    get_tool_export_profile,
    list_tool_export_profiles,
)

MAX_VERSION_BYTES = 64 * 1024
MAX_HELP_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 300.0
logger = get_logger(__name__)


class ToolchainExporter:
    """Run explicit tool profiles without loading raw output into memory."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        identity_catalog: SourceIdentityCatalog | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.identity_catalog = identity_catalog or SourceIdentityCatalog()
        self.last_cache_hit = False

    def export(
        self,
        source_path: Path,
        tool_path: Path,
        profile_name: str,
        output_dir: Path,
    ) -> ToolExport:
        """Resolve a named profile and publish one durable raw export."""
        return self.export_profile(
            source_path,
            tool_path,
            get_tool_export_profile(profile_name),
            output_dir,
        )

    def export_profile(
        self,
        source_path: Path,
        tool_path: Path,
        profile: ToolExportProfile,
        output_dir: Path,
    ) -> ToolExport:
        """Publish one profile using a staged directory and atomic rename."""
        source, tool = self._validate_inputs(source_path, tool_path)
        source_identity = self.identity_catalog.identify(source)
        tool_identity = self.identity_catalog.identify(tool)
        artifact_key = self._artifact_key(source_identity.sha256, tool_identity.sha256, profile)
        output_dir.mkdir(parents=True, exist_ok=True)
        final_dir = output_dir / artifact_key
        cached = self._load_cached(final_dir, artifact_key)
        if cached is not None:
            self.last_cache_hit = True
            return cached

        self.last_cache_hit = False
        stage_dir = output_dir / f".{artifact_key}.staging-{uuid4().hex}"
        stage_dir.mkdir(parents=False)
        try:
            export = self._run_profile(
                source,
                tool,
                source_identity,
                tool_identity,
                profile,
                artifact_key,
                stage_dir,
            )
            self._publish_export(stage_dir, final_dir, export)
            return export
        except BaseException:
            _remove_staging_directory(stage_dir, output_dir)
            raise

    @staticmethod
    def _validate_inputs(source_path: Path, tool_path: Path) -> tuple[Path, Path]:
        source = source_path.resolve()
        tool = tool_path.resolve()
        if not source.is_file():
            raise ValueError(f"Tool export source not found: {source}")
        if not tool.is_file():
            raise ValueError(f"Tool executable not found: {tool}")
        return source, tool

    def _run_profile(
        self,
        source: Path,
        tool: Path,
        source_identity: SourceIdentity,
        tool_identity: SourceIdentity,
        profile: ToolExportProfile,
        artifact_key: str,
        stage_dir: Path,
    ) -> ToolExport:
        version_path = stage_dir / "version.txt"
        version_result = _run_to_file(
            tool,
            ("--version",),
            version_path,
            self.timeout_seconds,
            max_output_bytes=MAX_VERSION_BYTES,
            merge_stderr=True,
        )
        self._require_success(tool, ("--version",), version_result)
        output_path = stage_dir / f"export.{_output_suffix(profile.output_format)}"
        arguments = (*profile.arguments, str(source))
        export_result = _run_to_file(
            tool,
            arguments,
            output_path,
            self.timeout_seconds,
            max_output_bytes=profile.max_output_bytes,
        )
        self._require_success(tool, arguments, export_result)
        if export_result.stdout_truncated:
            raise ToolchainExportError(
                f"External tool output exceeded the {profile.max_output_bytes} byte cap: "
                f"{profile.name}"
            )
        return ToolExport(
            artifact_key=artifact_key,
            source_path=str(source),
            source_sha256=source_identity.sha256,
            source_size=source_identity.size,
            tool_name=profile.tool_name,
            tool_path=str(tool),
            tool_sha256=tool_identity.sha256,
            tool_version=_read_version(version_path),
            profile=profile.name,
            arguments=profile.arguments,
            authority=profile.authority,
            output=ToolExportOutput(
                path=output_path.name,
                sha256=sha256_file(output_path),
                size=output_path.stat().st_size,
                format=profile.output_format,
            ),
            max_output_bytes=profile.max_output_bytes,
            diagnostics=(),
        )

    @staticmethod
    def _publish_export(stage_dir: Path, final_dir: Path, export: ToolExport) -> None:
        _write_json(stage_dir / "manifest.json", export.to_dict())
        if final_dir.exists():
            raise ValueError(f"Unvalidated tool export already exists: {final_dir}")
        stage_dir.replace(final_dir)
        assert export.output is not None
        log_event(
            logger,
            logging.INFO,
            "tool_export_published",
            artifact_key=export.artifact_key,
            profile=export.profile,
            output_path=final_dir / export.output.path,
            output_size=export.output.size,
        )

    @staticmethod
    def _artifact_key(source_sha256: str, tool_sha256: str, profile: ToolExportProfile) -> str:
        payload = {
            "schema_version": TOOL_EXPORT_SCHEMA_VERSION,
            "source_sha256": source_sha256,
            "tool_sha256": tool_sha256,
            "profile": profile.name,
            "tool_name": profile.tool_name,
            "arguments": profile.arguments,
            "output_format": profile.output_format,
            "authority": profile.authority,
            "max_output_bytes": profile.max_output_bytes,
        }
        return canonical_tool_export_key(payload)

    @staticmethod
    def _load_cached(path: Path, artifact_key: str) -> ToolExport | None:
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            export = ToolExport.from_dict(
                value, manifest_name=manifest_path.name
            ).require_complete()
            if export.artifact_key != artifact_key or export.output is None:
                raise ValueError("artifact key or output descriptor mismatch")
            output_path = _safe_output_path(path, export.output.path)
            _validate_output(output_path, export.output)
            return export
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"Existing tool export is invalid: {manifest_path}") from error

    @staticmethod
    def _require_success(
        tool: Path, arguments: tuple[str, ...], result: BoundedCommandResult
    ) -> None:
        if result.returncode == 0:
            return
        detail = result.stderr_preview or "no diagnostic"
        command = " ".join((tool.name, *arguments))
        raise ToolchainExportError(
            f"External tool failed ({result.returncode}): {command}: {detail}"
        )


def load_tool_exports(
    manifest_paths: tuple[Path, ...],
    source_path: Path,
    identity_catalog: SourceIdentityCatalog | None = None,
) -> tuple[ToolExport, ...]:
    """Load complete exports and reject stale or path-escaping artifacts."""
    if not manifest_paths:
        return ()
    catalog = identity_catalog or SourceIdentityCatalog()
    source_identity = catalog.identify(source_path)
    exports: list[ToolExport] = []
    seen_keys: set[str] = set()
    for manifest_path in manifest_paths:
        path = manifest_path.resolve()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            export = ToolExport.from_dict(value, manifest_name=path.name).require_complete()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid tool export manifest: {path}") from error
        if export.artifact_key in seen_keys:
            raise ValueError(f"Duplicate tool export artifact key: {export.artifact_key}")
        if export.source_sha256 != source_identity.sha256:
            raise ValueError(f"Tool export source does not match {source_path}: {path}")
        if export.source_size != source_identity.size:
            raise ValueError(f"Tool export source size does not match {source_path}: {path}")
        if export.artifact_key != _artifact_key_from_export(export):
            raise ValueError(f"Tool export artifact key does not match its manifest: {path}")
        if export.output is None:
            raise ValueError(f"Tool export has no output: {path}")
        output_path = _safe_output_path(path.parent, export.output.path)
        _validate_output(output_path, export.output)
        seen_keys.add(export.artifact_key)
        exports.append(export)
    return tuple(sorted(exports, key=lambda item: item.artifact_key))


def _artifact_key_from_export(export: ToolExport) -> str:
    """Recompute the content key embedded in a persisted export manifest."""
    if export.output is None:
        raise ValueError(f"Tool export has no output: {export.artifact_key}")
    return canonical_tool_export_key(
        {
            "schema_version": TOOL_EXPORT_SCHEMA_VERSION,
            "source_sha256": export.source_sha256,
            "tool_sha256": export.tool_sha256,
            "profile": export.profile,
            "tool_name": export.tool_name,
            "arguments": export.arguments,
            "output_format": export.output.format,
            "authority": export.authority,
            "max_output_bytes": export.max_output_bytes,
        }
    )


def probe_tool(
    tool_path: Path,
    output_dir: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    identity_catalog: SourceIdentityCatalog | None = None,
) -> dict[str, object]:
    """Capture bounded version/help artifacts for a tool without an input binary."""
    tool = tool_path.resolve()
    if not tool.is_file():
        raise ValueError(f"Tool executable not found: {tool}")
    catalog = identity_catalog or SourceIdentityCatalog()
    identity = catalog.identify(tool)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", tool.stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe_name = f"{safe_name}-v{TOOL_EXPORT_SCHEMA_VERSION}-{identity.sha256[:16]}"
    final_dir = output_dir / probe_name
    probe_path = final_dir / "probe.json"
    if probe_path.is_file():
        return _load_cached_probe(final_dir, probe_path)
    stage_dir = output_dir / f".{probe_name}.staging-{uuid4().hex}"
    stage_dir.mkdir(parents=False)
    try:
        result = _capture_probe(tool, identity, stage_dir, timeout_seconds)
        _write_json(stage_dir / "probe.json", result)
        if final_dir.exists():
            raise ValueError(f"Unvalidated tool probe already exists: {final_dir}")
        stage_dir.replace(final_dir)
        return result
    except BaseException:
        _remove_staging_directory(stage_dir, output_dir)
        raise


def _capture_probe(
    tool: Path,
    identity: SourceIdentity,
    stage_dir: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    """Capture and describe the bounded version/help files for one tool."""
    version_path = stage_dir / "version.txt"
    help_path = stage_dir / "help.txt"
    version_result = _run_to_file(
        tool,
        ("--version",),
        version_path,
        timeout_seconds,
        max_output_bytes=MAX_VERSION_BYTES,
        merge_stderr=True,
    )
    help_result = _run_to_file(
        tool,
        ("--help",),
        help_path,
        timeout_seconds,
        max_output_bytes=MAX_HELP_BYTES,
        merge_stderr=True,
    )
    if version_result.returncode != 0:
        raise ToolchainExportError(f"Tool version probe failed: {tool.name}")
    if help_result.returncode != 0:
        raise ToolchainExportError(f"Tool help probe failed: {tool.name}")
    if version_result.stdout_truncated:
        raise ToolchainExportError(f"Tool version output exceeded its bound: {tool.name}")
    if help_result.stdout_truncated:
        raise ToolchainExportError(f"Tool help output exceeded its bound: {tool.name}")
    return {
        "schema_version": TOOL_EXPORT_SCHEMA_VERSION,
        "status": "complete",
        "tool": {
            "name": tool.name,
            "path": str(tool),
            "sha256": identity.sha256,
            "size": identity.size,
            "version": _read_version(version_path),
        },
        "help": {
            "path": help_path.name,
            "sha256": sha256_file(help_path),
            "size": help_path.stat().st_size,
            "truncated": help_result.stdout_truncated,
        },
        "profiles": [profile.name for profile in list_tool_export_profiles()],
    }


def _read_version(path: Path) -> str:
    lines = [line.strip() for line in _read_text_prefix(path).splitlines() if line.strip()]
    return " | ".join(lines[:2]) or "unknown"


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _load_cached_probe(final_dir: Path, probe_path: Path) -> dict[str, object]:
    """Validate the bounded help artifact before reusing a probe."""
    result = _read_json(probe_path)
    if (
        result.get("schema_version") != TOOL_EXPORT_SCHEMA_VERSION
        or result.get("status") != "complete"
    ):
        raise ValueError(f"Cached tool probe is incomplete or stale: {probe_path}")
    help_value = result.get("help")
    if not isinstance(help_value, dict):
        raise ValueError(f"Cached tool probe has no help descriptor: {probe_path}")
    help_path = help_value.get("path")
    help_sha256 = help_value.get("sha256")
    help_size = help_value.get("size")
    if (
        not isinstance(help_path, str)
        or not isinstance(help_sha256, str)
        or isinstance(help_size, bool)
        or not isinstance(help_size, int)
        or help_size < 0
    ):
        raise ValueError(f"Cached tool probe has an invalid help descriptor: {probe_path}")
    _validate_output(
        _safe_output_path(final_dir, help_path),
        ToolExportOutput(help_path, help_sha256, help_size, "text"),
    )
    return result


def _safe_output_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"Tool export output escapes its manifest directory: {relative_path}")
    return candidate


def _validate_output(path: Path, descriptor: ToolExportOutput) -> None:
    if not path.is_file():
        raise ValueError(f"Tool export output not found: {path}")
    if path.stat().st_size != descriptor.size:
        raise ValueError(f"Tool export output size changed: {path}")
    if sha256_file(path) != descriptor.sha256:
        raise ValueError(f"Tool export output checksum changed: {path}")


def _output_suffix(output_format: str) -> str:
    return {"json": "json", "jsonl": "jsonl"}.get(output_format, "txt")


def _remove_staging_directory(stage_dir: Path, output_dir: Path) -> None:
    """Remove only the uniquely named staging directory created below output_dir."""
    if stage_dir.parent.resolve() != output_dir.resolve() or not stage_dir.name.startswith("."):
        return
    shutil.rmtree(stage_dir, ignore_errors=True)

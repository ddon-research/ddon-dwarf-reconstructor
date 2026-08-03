"""Source-bound evidence records produced by external inspection tools."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

TOOL_EXPORT_SCHEMA_VERSION = "1.1"


@dataclass(frozen=True, slots=True)
class ToolExportOutput:
    """The durable raw output attached to one tool export manifest."""

    path: str
    sha256: str
    size: int
    format: str

    def to_dict(self) -> dict[str, object]:
        """Return the stable machine-readable output descriptor."""
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "format": self.format,
        }


@dataclass(frozen=True, slots=True)
class ToolExport:
    """One immutable, source-bound external-tool export."""

    artifact_key: str
    source_path: str
    source_sha256: str
    source_size: int
    tool_name: str
    tool_path: str
    tool_sha256: str
    tool_version: str
    profile: str
    arguments: tuple[str, ...]
    authority: str
    output: ToolExportOutput | None
    max_output_bytes: int | None = None
    status: str = "complete"
    diagnostics: tuple[str, ...] = ()
    manifest_name: str = "manifest.json"

    def to_dict(self) -> dict[str, object]:
        """Return a stable manifest payload without machine-local manifest paths."""
        return {
            "schema_version": TOOL_EXPORT_SCHEMA_VERSION,
            "artifact_key": self.artifact_key,
            "source": {
                "path": self.source_path,
                "sha256": self.source_sha256,
                "size": self.source_size,
            },
            "tool": {
                "name": self.tool_name,
                "path": self.tool_path,
                "sha256": self.tool_sha256,
                "version": self.tool_version,
            },
            "profile": self.profile,
            "arguments": list(self.arguments),
            "authority": self.authority,
            "max_output_bytes": self.max_output_bytes,
            "status": self.status,
            "diagnostics": list(self.diagnostics),
            "output": None if self.output is None else self.output.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
        *,
        manifest_name: str = "manifest.json",
    ) -> ToolExport:
        """Restore and validate one manifest payload."""
        if value.get("schema_version") != TOOL_EXPORT_SCHEMA_VERSION:
            raise ValueError("Unsupported tool export schema version")
        source = _mapping(value, "source")
        tool = _mapping(value, "tool")
        output_value = value.get("output")
        output = None
        if output_value is not None:
            output_mapping = _as_mapping(output_value, "output")
            output = ToolExportOutput(
                path=_string(output_mapping, "path"),
                sha256=_string(output_mapping, "sha256"),
                size=_integer(output_mapping, "size"),
                format=_string(output_mapping, "format"),
            )
        arguments = value.get("arguments", [])
        if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
            raise ValueError("Tool export arguments must be a string list")
        diagnostics = value.get("diagnostics", [])
        if not isinstance(diagnostics, list) or not all(
            isinstance(item, str) for item in diagnostics
        ):
            raise ValueError("Tool export diagnostics must be a string list")
        max_output_bytes = _optional_positive_integer(value, "max_output_bytes")
        return cls(
            artifact_key=_string(value, "artifact_key"),
            source_path=_string(source, "path"),
            source_sha256=_string(source, "sha256"),
            source_size=_integer(source, "size"),
            tool_name=_string(tool, "name"),
            tool_path=_string(tool, "path"),
            tool_sha256=_string(tool, "sha256"),
            tool_version=_string(tool, "version"),
            profile=_string(value, "profile"),
            arguments=tuple(arguments),
            authority=_string(value, "authority"),
            output=output,
            max_output_bytes=max_output_bytes,
            status=_string(value, "status"),
            diagnostics=tuple(diagnostics),
            manifest_name=manifest_name,
        )

    def require_complete(self) -> ToolExport:
        """Reject incomplete exports before they enter a knowledge bundle."""
        if self.status != "complete" or self.output is None:
            raise ValueError(f"Tool export {self.artifact_key} is not complete: {self.status}")
        return self


def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    """Read a required nested object from a manifest payload."""
    return _as_mapping(value.get(key), key)


def _as_mapping(value: object, key: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Tool export {key} must be an object")
    return cast(Mapping[str, object], value)


def _string(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"Tool export {key} must be a non-empty string")
    return result


def _integer(value: Mapping[str, object], key: str) -> int:
    result = value.get(key)
    if isinstance(result, bool) or not isinstance(result, int) or result < 0:
        raise ValueError(f"Tool export {key} must be a non-negative integer")
    return result


def _optional_positive_integer(value: Mapping[str, object], key: str) -> int | None:
    result = value.get(key)
    if result is None:
        return None
    if isinstance(result, bool) or not isinstance(result, int) or result <= 0:
        raise ValueError(f"Tool export {key} must be positive or null")
    return result


def canonical_tool_export_key(payload: Mapping[str, object]) -> str:
    """Return a stable identity for source, tool, profile, and command semantics."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

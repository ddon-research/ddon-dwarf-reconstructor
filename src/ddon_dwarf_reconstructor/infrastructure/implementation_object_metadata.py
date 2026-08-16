"""Object-header and optional Orbis-readelf evidence without stream artifacts."""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.implementation_validation import ValidationStatus


def collect_object_metadata(
    object_path: Path,
    readelf: Path | None,
    output_dir: Path,
    stem: str,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Record object metadata and readelf hashes without writing tool streams."""
    del output_dir, stem
    if not object_path.exists():
        return {}
    metadata = _object_header_metadata(object_path)
    if readelf is None:
        metadata["readelf_status"] = ValidationStatus.NOT_OBSERVED.value
        return metadata
    if not readelf.exists():
        metadata.update(
            {
                "readelf_status": ValidationStatus.UNAVAILABLE.value,
                "readelf_diagnostics": "Orbis readelf path does not exist",
            }
        )
        return metadata
    return _readelf_metadata(metadata, object_path, readelf, timeout_seconds)


def _object_header_metadata(object_path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {"size_bytes": object_path.stat().st_size}
    try:
        with object_path.open("rb") as stream:
            elf = ELFFile(stream)
            header = elf.header
            text_section = elf.get_section_by_name(".text")
            metadata.update(
                {
                    "elf_class": str(header["e_ident"]["EI_CLASS"]),
                    "machine": str(header["e_machine"]),
                    "type": str(header["e_type"]),
                    "text_size": text_section.header["sh_size"]
                    if text_section is not None
                    else None,
                }
            )
    except ELFError, OSError, ValueError, KeyError:
        metadata["parser_status"] = "unavailable"
    return metadata


def _readelf_metadata(
    metadata: dict[str, object],
    object_path: Path,
    readelf: Path,
    timeout_seconds: float | None,
) -> dict[str, object]:
    command = (str(readelf), "-h", "-S", "-r", str(object_path))
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
                "readelf_status": ValidationStatus.BLOCKED.value,
                "readelf_command": command,
                "timeout": _timeout_metadata(str(readelf), "readelf", started, timeout_seconds),
            }
        )
        return metadata
    except OSError as error:
        metadata.update(
            {
                "readelf_status": ValidationStatus.UNAVAILABLE.value,
                "readelf_command": command,
                "readelf_diagnostics": type(error).__name__,
            }
        )
        return metadata
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    metadata.update(
        {
            "readelf_status": (
                ValidationStatus.OBSERVED.value
                if completed.returncode == 0
                else ValidationStatus.FAILED.value
            ),
            "readelf_tool_sha256": _sha256_file(readelf),
            "readelf_version": _tool_version(readelf, timeout_seconds),
            "readelf_command": command,
            "readelf_stdout_sha256": _sha256_text(stdout),
            "readelf_stderr_sha256": _sha256_text(stderr),
        }
    )
    return metadata


def _tool_version(path: Path, timeout_seconds: float | None) -> str | None:
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


__all__ = ["collect_object_metadata"]

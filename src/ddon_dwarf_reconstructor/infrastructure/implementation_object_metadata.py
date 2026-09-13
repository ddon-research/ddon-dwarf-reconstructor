"""Object-header and optional Orbis-readelf evidence without stream artifacts."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..core.content_hash import sha256_text
from ..domain.models.implementation_validation import ValidationStatus
from .toolchain_process import (
    ToolchainExportError,
    ToolIdentityCache,
    run_bounded_capture,
)
from .toolchain_process import timeout_metadata as _timeout_metadata


def collect_object_metadata(
    object_path: Path,
    readelf: Path | None,
    *,
    timeout_seconds: float | None = None,
    identity_cache: ToolIdentityCache | None = None,
) -> dict[str, object]:
    """Record object metadata and readelf hashes without writing tool streams."""
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
    return _readelf_metadata(
        metadata,
        object_path,
        readelf,
        timeout_seconds,
        identity_cache=identity_cache,
    )


def _object_header_metadata(object_path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {"size_bytes": object_path.stat().st_size}
    try:
        with object_path.open("rb") as stream:
            metadata.update(_section_metadata(ELFFile(stream)))
    except ELFError, OSError, ValueError, KeyError:
        metadata["parser_status"] = "unavailable"
    return metadata


def _section_metadata(elf: Any) -> dict[str, object]:
    header = elf.header
    sections = tuple(elf.get_section(index) for index in range(elf.num_sections()))
    names, sizes = _section_names_and_sizes(sections)
    flags = int(header["e_flags"])
    text = elf.get_section_by_name(".text")
    return {
        "elf_class": str(header["e_ident"]["EI_CLASS"]),
        "machine": str(header["e_machine"]),
        "type": str(header["e_type"]),
        "e_flags": flags,
        "section_names": names,
        "section_sizes": sizes,
        "text_size": text.header["sh_size"] if text is not None else None,
        "function_data_sections_enabled": bool(flags & 0x04000000),
        "has_sce_stack_sizes": ".sce_stack_sizes" in names,
        "has_sce_stack_size_relocations": ".rela.sce_stack_sizes" in names,
        "has_eh_frame": ".eh_frame" in names,
        "has_debug_frame": ".debug_frame" in names,
        "has_debug_aranges": ".debug_aranges" in names,
        "has_debug_ranges": ".debug_ranges" in names,
        "debug_range_sections": _matching_sections(
            names, {".debug_ranges", ".debug_rnglists", ".debug_loc", ".debug_loclists"}
        ),
        "text_subsections": _prefixed_sections(names, (".text.",)),
        "data_subsections": _prefixed_sections(names, (".data.", ".rodata.")),
    }


def _section_names_and_sizes(
    sections: tuple[Any, ...],
) -> tuple[tuple[str, ...], dict[str, int]]:
    names = tuple(section.name for section in sections)
    sizes = {section.name: section.header["sh_size"] for section in sections}
    return names, sizes


def _matching_sections(names: tuple[str, ...], wanted: set[str]) -> tuple[str, ...]:
    return tuple(name for name in names if name in wanted)


def _prefixed_sections(names: tuple[str, ...], prefixes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if name.startswith(prefixes))


def _readelf_metadata(
    metadata: dict[str, object],
    object_path: Path,
    readelf: Path,
    timeout_seconds: float | None,
    *,
    identity_cache: ToolIdentityCache | None = None,
) -> dict[str, object]:
    command = (str(readelf), "-h", "-S", "-r", str(object_path))
    started = time.perf_counter()
    try:
        completed = run_bounded_capture(
            readelf,
            command[1:],
            timeout_seconds,
        )
    except TimeoutError:
        metadata.update(
            {
                "readelf_status": ValidationStatus.BLOCKED.value,
                "readelf_command": command,
                "timeout": _timeout_metadata(str(readelf), "readelf", started, timeout_seconds),
            }
        )
        return metadata
    except (OSError, ToolchainExportError) as error:
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
    identity = (identity_cache or ToolIdentityCache()).observe(
        readelf,
        timeout_seconds,
        profile="readelf",
    )
    metadata.update(
        {
            "readelf_status": (
                ValidationStatus.OBSERVED.value
                if completed.returncode == 0
                else ValidationStatus.FAILED.value
            ),
            "readelf_tool_sha256": identity.sha256,
            "readelf_version": identity.version,
            "readelf_command": command,
            "readelf_stdout_sha256": sha256_text(stdout),
            "readelf_stderr_sha256": sha256_text(stderr),
        }
    )
    if completed.stdout_truncated or completed.stderr_truncated:
        metadata["readelf_status"] = ValidationStatus.FAILED.value
        metadata["readelf_diagnostics"] = "Orbis readelf output exceeded the bounded cap"
    return metadata


__all__ = ["collect_object_metadata"]

"""ELF PT_LOAD geometry and explicit PS4 load-bias evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

from ..domain.models.implementation_validation import (
    LoadImageProfile,
    MappedSegment,
    ValidationStatus,
)
from .orbis_sdk_definitions import ORBIS_COMMON_PAGE_SIZE

_MAX_ADDRESS = 1 << 64


def read_load_image(
    source: Path,
    *,
    requested_base: int | None,
    original_addresses: bool,
) -> tuple[LoadImageProfile, tuple[MappedSegment, ...]]:
    """Read PT_LOAD geometry without mapping or modifying the ELF."""
    headers = _load_headers(source)
    if not headers:
        profile = LoadImageProfile(
            "original-addresses" if original_addresses else "explicit-load-base",
            requested_base,
            None,
            None,
            None,
            ValidationStatus.FAILED,
            ("ELF contains no PT_LOAD segments",),
        )
        return profile, ()

    minimum = min(int(header["p_vaddr"]) for header in headers)
    required_alignment = _required_alignment(headers)
    diagnostics = _header_geometry_diagnostics(headers, source.stat().st_size)
    diagnostics.extend(_alignment_diagnostics(headers))
    policy, effective_base, bias, status, policy_diagnostics = _resolve_load_policy(
        minimum,
        required_alignment,
        requested_base,
        original_addresses,
    )
    diagnostics.extend(policy_diagnostics)

    segments = tuple(_segment(index, header, bias) for index, header in enumerate(headers))
    status = _validate_segments(status, segments, diagnostics)
    profile = LoadImageProfile(
        policy,
        effective_base,
        minimum,
        bias,
        required_alignment,
        status,
        tuple(diagnostics),
    )
    return profile, segments


def _load_headers(source: Path) -> list[Any]:
    with source.open("rb") as stream:
        elf = ELFFile(stream)
        return [segment.header for segment in elf.iter_segments() if _is_load(segment)]


def _required_alignment(headers: list[Any]) -> int:
    alignments = (int(header["p_align"]) for header in headers if int(header["p_align"]) > 0)
    return max(ORBIS_COMMON_PAGE_SIZE, max(alignments, default=ORBIS_COMMON_PAGE_SIZE))


def _validate_segments(
    status: ValidationStatus, segments: tuple[MappedSegment, ...], diagnostics: list[str]
) -> ValidationStatus:
    if _has_file_size_failure(segments):
        diagnostics.append("one or more PT_LOAD segments have p_filesz greater than p_memsz")
        return ValidationStatus.FAILED
    if _has_address_overflow(segments):
        diagnostics.append("one or more PT_LOAD segments overflow the 64-bit address domain")
        return ValidationStatus.FAILED
    if _has_runtime_overflow(segments):
        diagnostics.append(
            "one or more runtime PT_LOAD mappings overflow the 64-bit address domain"
        )
        return ValidationStatus.FAILED
    return ValidationStatus.FAILED if _has_segment_diagnostic(diagnostics) else status


def _has_file_size_failure(segments: tuple[MappedSegment, ...]) -> bool:
    return any(segment.file_size > segment.memory_size for segment in segments)


def _has_address_overflow(segments: tuple[MappedSegment, ...]) -> bool:
    return any(
        segment.virtual_address + segment.memory_size >= _MAX_ADDRESS
        or segment.file_offset + segment.file_size >= _MAX_ADDRESS
        for segment in segments
    )


def _has_runtime_overflow(segments: tuple[MappedSegment, ...]) -> bool:
    return any(
        segment.runtime_start is not None
        and (segment.runtime_start < 0 or (segment.runtime_memory_end or 0) >= _MAX_ADDRESS)
        for segment in segments
    )


def _has_segment_diagnostic(diagnostics: list[str]) -> bool:
    return any("PT_LOAD" in diagnostic for diagnostic in diagnostics)


def _alignment_diagnostics(headers: list[Any]) -> list[str]:
    diagnostics: list[str] = []
    for index, header in enumerate(headers):
        alignment = int(header["p_align"])
        if alignment > 1 and alignment & (alignment - 1):
            diagnostics.append(f"PT_LOAD {index} has non-power-of-two p_align")
        if (
            alignment > 1
            and int(header["p_vaddr"]) % alignment != int(header["p_offset"]) % alignment
        ):
            diagnostics.append(f"PT_LOAD {index} virtual/file alignment is inconsistent")
    return diagnostics


def _header_geometry_diagnostics(headers: list[Any], source_size: int) -> list[str]:
    diagnostics: list[str] = []
    for index, header in enumerate(headers):
        file_offset = int(header["p_offset"])
        virtual_address = int(header["p_vaddr"])
        file_size = int(header["p_filesz"])
        memory_size = int(header["p_memsz"])
        if min(file_offset, virtual_address, file_size, memory_size) < 0:
            diagnostics.append(f"PT_LOAD {index} contains a negative geometry value")
        if file_offset + file_size > source_size:
            diagnostics.append(f"PT_LOAD {index} extends beyond the ELF file")
        if virtual_address + memory_size >= _MAX_ADDRESS:
            diagnostics.append(f"PT_LOAD {index} overflows the 64-bit virtual address domain")
        if file_size > memory_size:
            diagnostics.append(f"PT_LOAD {index} has p_filesz greater than p_memsz")
    return diagnostics


def _resolve_load_policy(
    minimum: int,
    required_alignment: int,
    requested_base: int | None,
    original_addresses: bool,
) -> tuple[str, int | None, int | None, ValidationStatus, tuple[str, ...]]:
    policy = "original-addresses" if original_addresses else "explicit-load-base"
    diagnostics: list[str] = []
    if original_addresses:
        if requested_base is not None:
            diagnostics.append("requested load base ignored by original-addresses policy")
        return policy, requested_base, 0, ValidationStatus.OBSERVED, tuple(diagnostics)
    if requested_base is None:
        diagnostics.append("runtime load base was not supplied")
        return policy, None, None, ValidationStatus.NOT_OBSERVED, tuple(diagnostics)
    if requested_base < 0 or requested_base >= _MAX_ADDRESS:
        diagnostics.append("runtime load base is outside the 64-bit address domain")
        return policy, requested_base, None, ValidationStatus.FAILED, tuple(diagnostics)
    bias = requested_base - minimum
    if requested_base % required_alignment:
        diagnostics.append(
            f"load base 0x{requested_base:x} is not aligned to 0x{required_alignment:x}"
        )
        return policy, requested_base, bias, ValidationStatus.FAILED, tuple(diagnostics)
    return policy, requested_base, bias, ValidationStatus.OBSERVED, tuple(diagnostics)


def virtual_to_file_offset(
    segments: tuple[MappedSegment, ...], virtual_address: int, width: int
) -> int | None:
    """Map an ELF virtual address into a PT_LOAD file range."""
    if width <= 0 or virtual_address < 0 or virtual_address >= _MAX_ADDRESS:
        return None
    for segment in segments:
        start = segment.virtual_address
        end = start + segment.file_size
        if (
            start <= virtual_address
            and virtual_address + width < _MAX_ADDRESS
            and virtual_address + width <= end
        ):
            return segment.file_offset + virtual_address - start
    return None


def runtime_address(profile: LoadImageProfile, virtual_address: int) -> int | None:
    """Apply only the explicitly selected load bias."""
    if profile.load_bias is None:
        return None
    value = virtual_address + profile.load_bias
    return value if 0 <= value < _MAX_ADDRESS else None


def _is_load(segment: Any) -> bool:
    value = segment.header["p_type"]
    return value == "PT_LOAD" or value == 1


def _segment(index: int, header: Any, bias: int | None) -> MappedSegment:
    file_offset = int(header["p_offset"])
    virtual_address = int(header["p_vaddr"])
    file_size = int(header["p_filesz"])
    memory_size = int(header["p_memsz"])
    runtime_start = virtual_address + bias if bias is not None else None
    runtime_file_end = runtime_start + file_size if runtime_start is not None else None
    runtime_memory_end = runtime_start + memory_size if runtime_start is not None else None
    return MappedSegment(
        index=index,
        flags=int(header["p_flags"]),
        file_offset=file_offset,
        virtual_address=virtual_address,
        file_size=file_size,
        memory_size=memory_size,
        alignment=int(header["p_align"]),
        runtime_start=runtime_start,
        runtime_file_end=runtime_file_end,
        runtime_memory_end=runtime_memory_end,
    )


__all__ = ["read_load_image", "runtime_address", "virtual_to_file_offset"]

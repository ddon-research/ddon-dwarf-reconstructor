"""Source-bound CFI range inspection for implementation validation."""

from __future__ import annotations

from pathlib import Path

from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

from ..domain.models.implementation_validation import EvidenceStatus, ValidationStatus


def inspect_cfi(source: Path, start: int, size: int) -> EvidenceStatus:
    """Locate CFI covering a method range without treating absence as success."""
    if size <= 0:
        return EvidenceStatus(ValidationStatus.NOT_OBSERVED, ("method range is empty",))
    entries, error = _read_cfi_entries(source)
    if error is not None:
        return error
    end = start + size
    spans = sorted(span for entry in entries if (span := _cfi_span(entry, start, end)) is not None)
    if not spans:
        return EvidenceStatus(
            ValidationStatus.NOT_OBSERVED,
            ("no .debug_frame or .eh_frame entry covers the method range",),
        )
    gaps = _cfi_gaps(spans, start, end)
    if gaps:
        return EvidenceStatus(
            ValidationStatus.PARTIAL,
            ("CFI entries overlap the method but do not join across its full range",),
            {"covering_entries": len(spans), "uncovered_ranges": gaps},
        )
    return EvidenceStatus(
        ValidationStatus.OBSERVED,
        details={"covering_entries": len(spans), "covered_range": (start, end)},
    )


def _read_cfi_entries(source: Path) -> tuple[tuple[object, ...], EvidenceStatus | None]:
    entries: list[object] = []
    try:
        with source.open("rb") as stream:
            dwarf = ELFFile(stream).get_dwarf_info()
            for getter_name in ("CFI_entries", "EH_CFI_entries"):
                getter = getattr(dwarf, getter_name, None)
                if getter is None:
                    continue
                try:
                    entries.extend(getter())
                except Exception as error:  # parser-specific diagnostics are evidence
                    return (), EvidenceStatus(
                        ValidationStatus.PARTIAL,
                        (f"{getter_name} parsing failed: {type(error).__name__}",),
                    )
    except (ELFError, OSError, ValueError) as error:
        return (), EvidenceStatus(
            ValidationStatus.UNAVAILABLE,
            (f"CFI source could not be opened: {type(error).__name__}",),
        )
    return tuple(entries), None


def _cfi_span(entry: object, start: int, end: int) -> tuple[int, int] | None:
    header = getattr(entry, "header", {})
    initial = _header_int(header, "initial_location")
    span = _header_int(header, "address_range")
    if initial is None or span is None or span <= 0:
        return None
    left = max(initial, start)
    right = min(initial + span, end)
    return (left, right) if left < right else None


def _cfi_gaps(spans: list[tuple[int, int]], start: int, end: int) -> tuple[tuple[int, int], ...]:
    cursor = start
    gaps: list[tuple[int, int]] = []
    for left, right in spans:
        if left > cursor:
            gaps.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append((cursor, end))
    return tuple(gaps)


def _header_int(header: object, key: str) -> int | None:
    try:
        value = header[key]  # type: ignore[index]
    except KeyError, TypeError:
        return None
    return int(value) if value is not None else None


__all__ = ["inspect_cfi"]

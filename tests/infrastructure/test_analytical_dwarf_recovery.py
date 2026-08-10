"""Tests for the guarded source-bound DWARF recovery overlay."""

from __future__ import annotations

from io import BytesIO

import pytest
from elftools.dwarf.dwarfinfo import DebugSectionDescriptor

from ddon_dwarf_reconstructor.infrastructure.analytical.dwarf_recovery import (
    apply_source_bound_dwarf_recovery,
    required_recovery_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]

_SOURCE_SHA256 = "4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0"
_MAX_OFFSET = 0x0802B2B6 + 6


class _DwarfInfo:
    def __init__(self, data: bytes) -> None:
        self.debug_info_sec = DebugSectionDescriptor(
            stream=BytesIO(data),
            name=".debug_info",
            global_offset=0,
            size=len(data),
            address=0,
        )


def _source_bytes() -> bytearray:
    data = bytearray(_MAX_OFFSET)
    for offset, value in {
        0x0802B28A: bytes.fromhex("d5 11 91 00 d2 00"),
        0x0802B29E: bytes.fromhex("81 b7 ad 00 d0 00"),
        0x0802B2B6: bytes.fromhex("d6 b7 ad 00 87 00"),
    }.items():
        data[offset : offset + len(value)] = value
    return data


def test_recovery_overlay_applies_only_to_the_known_source() -> None:
    dwarf_info = _DwarfInfo(_source_bytes())

    report = apply_source_bound_dwarf_recovery(dwarf_info, _SOURCE_SHA256)

    assert report.status == "applied"
    assert report.profile == required_recovery_profile(_SOURCE_SHA256)
    stream = dwarf_info.debug_info_sec.stream
    stream.seek(0x0802B28A)
    assert stream.read(6) == bytes.fromhex("0f 11 91 00 00 00")
    stream.seek(0x0802B29E)
    assert stream.read(6) == bytes.fromhex("0f b7 ad 00 00 00")
    stream.seek(0x0802B2B6)
    assert stream.read(6) == bytes.fromhex("0f b7 ad 00 00 00")


def test_recovery_rejects_a_changed_context() -> None:
    data = _source_bytes()
    data[0x0802B28A] = 0x00

    with pytest.raises(ValueError, match="context mismatch"):
        apply_source_bound_dwarf_recovery(_DwarfInfo(data), _SOURCE_SHA256)


def test_recovery_accepts_a_source_with_the_profile_already_applied() -> None:
    data = _source_bytes()
    for offset, value in {
        0x0802B28A: bytes.fromhex("0f 11 91 00 00 00"),
        0x0802B29E: bytes.fromhex("0f b7 ad 00 00 00"),
        0x0802B2B6: bytes.fromhex("0f b7 ad 00 00 00"),
    }.items():
        data[offset : offset + 6] = value

    dwarf_info = _DwarfInfo(data)
    report = apply_source_bound_dwarf_recovery(dwarf_info, _SOURCE_SHA256)

    assert report.status == "already_applied"
    assert report.profile == required_recovery_profile(_SOURCE_SHA256)
    stream = dwarf_info.debug_info_sec.stream
    stream.seek(0x0802B28A)
    assert stream.read(6) == bytes.fromhex("0f 11 91 00 00 00")


def test_recovery_rejects_partially_applied_contexts() -> None:
    data = _source_bytes()
    data[0x0802B28A : 0x0802B28A + 6] = bytes.fromhex("0f 11 91 00 00 00")

    with pytest.raises(ValueError, match="partially applied"):
        apply_source_bound_dwarf_recovery(_DwarfInfo(data), _SOURCE_SHA256)


def test_recovery_is_not_applied_to_an_unknown_source() -> None:
    dwarf_info = _DwarfInfo(_source_bytes())

    report = apply_source_bound_dwarf_recovery(dwarf_info, "unknown")

    assert report.status == "not_applicable"
    assert required_recovery_profile("unknown") is None
    stream = dwarf_info.debug_info_sec.stream
    stream.seek(0x0802B28A)
    assert stream.read(1) == b"\xd5"

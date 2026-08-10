"""Source-bound, evidence-backed overlays for known malformed DWARF bytes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DwarfRecoveryPatch:
    """One guarded replacement in the ``.debug_info`` section stream."""

    offset: int
    expected_prefix: bytes
    replacement_offset: int
    replacement_byte: int

    def to_dict(self) -> dict[str, Any]:
        """Return a manifest-safe description without exposing the whole section."""
        return {
            "offset": self.offset,
            "expected_prefix": self.expected_prefix.hex(),
            "replacement_offset": self.replacement_offset,
            "replacement_byte": self.replacement_byte,
        }


@dataclass(frozen=True, slots=True)
class DwarfRecoveryReport:
    """Provenance for an applied or unavailable source-bound recovery profile.

    ``already_applied`` means the source itself contains the exact repaired
    contexts recorded by the profile.  It is distinct from ``applied`` so the
    manifest can distinguish source bytes from an in-memory overlay.
    """

    status: str
    source_sha256: str
    profile: str | None
    evidence: str | None
    patches: tuple[DwarfRecoveryPatch, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic configuration metadata for the materialization manifest."""
        return {
            "status": self.status,
            "source_sha256": self.source_sha256,
            "profile": self.profile,
            "evidence": self.evidence,
            "patch_count": len(self.patches),
            "patches": [patch.to_dict() for patch in self.patches],
        }


class _OverlayStream:
    """Seekable read-through stream that substitutes a few guarded bytes."""

    def __init__(self, base: Any, replacements: dict[int, int]) -> None:
        self._base = base
        self._replacements = replacements

    def read(self, size: int = -1) -> bytes:
        start = self._base.tell()
        data = bytearray(self._base.read(size))
        for offset, value in self._replacements.items():
            index = offset - start
            if 0 <= index < len(data):
                data[index] = value
        return bytes(data)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._base.seek(offset, whence)

    def tell(self) -> int:
        return self._base.tell()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


_DDOORBIS_SOURCE_SHA256 = "4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0"
_RECOVERY_PROFILE = "ddoorbis-llvm-dump-formal-parameter-repair-v1"
_RECOVERY_EVIDENCE = (
    "D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst"
)
_PATCHES = (
    DwarfRecoveryPatch(
        offset=0x0802B28A,
        expected_prefix=bytes.fromhex("d5 11 91 00 d2 00"),
        replacement_offset=0x0802B28A,
        replacement_byte=0x0F,
    ),
    DwarfRecoveryPatch(
        offset=0x0802B28A,
        expected_prefix=bytes.fromhex("d5 11 91 00 d2 00"),
        replacement_offset=0x0802B28E,
        replacement_byte=0x00,
    ),
    DwarfRecoveryPatch(
        offset=0x0802B29E,
        expected_prefix=bytes.fromhex("81 b7 ad 00 d0 00"),
        replacement_offset=0x0802B29E,
        replacement_byte=0x0F,
    ),
    DwarfRecoveryPatch(
        offset=0x0802B29E,
        expected_prefix=bytes.fromhex("81 b7 ad 00 d0 00"),
        replacement_offset=0x0802B2A2,
        replacement_byte=0x00,
    ),
    DwarfRecoveryPatch(
        offset=0x0802B2B6,
        expected_prefix=bytes.fromhex("d6 b7 ad 00 87 00"),
        replacement_offset=0x0802B2B6,
        replacement_byte=0x0F,
    ),
    DwarfRecoveryPatch(
        offset=0x0802B2B6,
        expected_prefix=bytes.fromhex("d6 b7 ad 00 87 00"),
        replacement_offset=0x0802B2BA,
        replacement_byte=0x00,
    ),
)

_REPAIRED_CONTEXTS = {
    0x0802B28A: bytes.fromhex("0f 11 91 00 00 00"),
    0x0802B29E: bytes.fromhex("0f b7 ad 00 00 00"),
    0x0802B2B6: bytes.fromhex("0f b7 ad 00 00 00"),
}


def apply_source_bound_dwarf_recovery(
    dwarf_info: Any,
    source_sha256: str,
) -> DwarfRecoveryReport:
    """Apply the verified DDOORBIS repair profile, or leave other sources untouched."""
    if source_sha256 != _DDOORBIS_SOURCE_SHA256:
        return DwarfRecoveryReport("not_applicable", source_sha256, None, None)
    section = getattr(dwarf_info, "debug_info_sec", None)
    if section is None:
        raise ValueError("DWARF recovery requires a .debug_info section")
    stream = section.stream
    expected_contexts = {patch.offset: patch.expected_prefix for patch in _PATCHES}
    actual_contexts = {
        offset: _read_at(stream, offset, len(expected))
        for offset, expected in expected_contexts.items()
    }
    state = _recovery_context_state(actual_contexts, expected_contexts)
    if state == "original":
        return _apply_overlay(dwarf_info, section, stream, source_sha256)
    if state == "already_applied":
        return DwarfRecoveryReport(
            "already_applied",
            source_sha256,
            _RECOVERY_PROFILE,
            _RECOVERY_EVIDENCE,
            _PATCHES,
        )
    raise ValueError("Source-bound DWARF recovery contexts are only partially applied")


def _recovery_context_state(
    actual_contexts: dict[int, bytes],
    expected_contexts: dict[int, bytes],
) -> str:
    if all(actual_contexts[offset] == expected for offset, expected in expected_contexts.items()):
        return "original"
    if all(actual_contexts[offset] == _REPAIRED_CONTEXTS[offset] for offset in expected_contexts):
        return "already_applied"
    for offset, expected in expected_contexts.items():
        actual = actual_contexts[offset]
        if actual not in (expected, _REPAIRED_CONTEXTS[offset]):
            raise ValueError(
                "Source-bound DWARF recovery context mismatch at "
                f"0x{offset:x}: expected {expected.hex()} or "
                f"{_REPAIRED_CONTEXTS[offset].hex()}, got {actual.hex()}"
            )
    return "partial"


def _apply_overlay(
    dwarf_info: Any,
    section: Any,
    stream: Any,
    source_sha256: str,
) -> DwarfRecoveryReport:
    """Install the guarded overlay after all source contexts have been checked."""
    replacements: dict[int, int] = {}
    for patch in _PATCHES:
        replacements[patch.replacement_offset] = patch.replacement_byte
    dwarf_info.debug_info_sec = section._replace(stream=_OverlayStream(stream, replacements))
    return DwarfRecoveryReport(
        "applied",
        source_sha256,
        _RECOVERY_PROFILE,
        _RECOVERY_EVIDENCE,
        _PATCHES,
    )


def required_recovery_profile(source_sha256: str) -> str | None:
    """Return the recovery profile required for a source identity, if known."""
    return _RECOVERY_PROFILE if source_sha256 == _DDOORBIS_SOURCE_SHA256 else None


def _read_at(stream: Any, offset: int, size: int) -> bytes:
    position = stream.tell()
    try:
        stream.seek(offset)
        return bytes(stream.read(size))
    finally:
        stream.seek(position)

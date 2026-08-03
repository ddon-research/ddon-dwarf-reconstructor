"""Outbound source-identity contracts used by deterministic workflows."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


def source_metadata_lookup_key(size: int, mtime_ns: int, device: int, inode: int) -> str:
    """Return a relocation-stable key for an unchanged filesystem object.

    ``st_ctime_ns`` is deliberately excluded. POSIX filesystems update ctime when a
    file is renamed, even though its bytes, inode, size, and mtime are unchanged.
    The source catalog still retains ctime as a mutation signal and only tolerates
    its drift when the recorded path was actually relocated.
    """
    metadata = (size, mtime_ns, device, inode)
    return hashlib.sha256(":".join(str(value) for value in metadata).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Strong content identity paired with the metadata used for warm lookup."""

    sha256: str
    size: int
    mtime_ns: int
    ctime_ns: int
    device: int
    inode: int

    @property
    def lookup_key(self) -> str:
        """Return the relocation-stable key for the unchanged filesystem object."""
        return source_metadata_lookup_key(self.size, self.mtime_ns, self.device, self.inode)

    def as_fingerprint(self) -> dict[str, int | str]:
        """Return the source binding stored beside derived data."""
        return {key: value for key, value in asdict(self).items()}


class SourceIdentityPort(Protocol):
    """Resolve a source path to its durable content identity."""

    def identify(self, source_path: Path, *, verify: bool = False) -> SourceIdentity: ...


class SourceHashPort(Protocol):
    """Return the strong identity hash for an immutable source artifact."""

    def __call__(self, source_path: Path) -> str: ...

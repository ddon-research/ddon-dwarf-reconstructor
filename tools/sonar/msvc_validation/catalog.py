"""Deterministic typed catalogs of generated header artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HeaderCatalogEntry:
    """One generated header bound to its publishing bundle."""

    bundle: Path
    header: Path
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class HeaderCatalog:
    """Complete deterministic input catalog for per-header validation."""

    bundles: tuple[Path, ...]
    entries: tuple[HeaderCatalogEntry, ...]

    @property
    def bundle_count(self) -> int:
        return len(self.bundles)

    @property
    def header_count(self) -> int:
        return len(self.entries)


def build_header_catalog(bundles: tuple[Path, ...] | list[Path]) -> HeaderCatalog:
    """Hash every header once and preserve bundle/header ordering."""
    ordered_bundles = tuple(sorted(set(bundles), key=lambda path: str(path).lower()))
    entries = tuple(
        HeaderCatalogEntry(
            bundle=bundle,
            header=header,
            sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
            byte_count=header.stat().st_size,
        )
        for bundle in ordered_bundles
        for header in sorted(bundle.glob("*.h"), key=lambda path: path.name.lower())
    )
    if not entries:
        raise ValueError("No generated headers were found in the requested bundles")
    return HeaderCatalog(ordered_bundles, entries)

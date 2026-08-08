"""Generator session backed by a validated analytical DWARF store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.dwarf import DwarfInfo
from ...core.platform import ELFPlatform
from ...domain.ports.dwarf_lookup import DwarfLookupPort
from ..artifacts import SourceIdentityCatalog
from .jsonl_store import JsonlDwarfStore
from .manifest import load_manifest

if TYPE_CHECKING:
    from ...domain.ports.analytical_store import DwarfQueryPort


class AnalyticalDwarfSession:
    """Own one materialized store for the duration of a generation request."""

    # A store-backed runtime must never discover or consult the legacy dump
    # adapter implicitly.  Validation producers remain available only through
    # an explicit non-analytical session.
    legacy_lookup_allowed = False

    def __init__(
        self,
        manifest_path: Path,
        *,
        expected_source_path: Path | None = None,
        verify_source: bool = True,
        selection_cache_path: Path | None = None,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.expected_source_path = expected_source_path.resolve() if expected_source_path else None
        self.verify_source = verify_source
        self.selection_cache_path = (
            selection_cache_path.resolve() if selection_cache_path is not None else None
        )
        self.selection_source_fingerprint: dict[str, int | str] | None = None
        self.store: JsonlDwarfStore | None = None
        self.query_port: DwarfQueryPort | None = None
        self.query_index: DwarfLookupPort | None = None
        self.dwarf_info: DwarfInfo | None = None
        self.platform = ELFPlatform.UNKNOWN

    def __enter__(self) -> AnalyticalDwarfSession:
        source_identity = None
        if self.expected_source_path is not None and self.verify_source:
            source_identity = SourceIdentityCatalog().identify(self.expected_source_path)
            self.selection_source_fingerprint = source_identity.as_fingerprint()
        self.store = load_analytical_store(
            self.manifest_path,
            verify_source=self.verify_source,
            source_path=self.expected_source_path,
            selection_cache_path=self.selection_cache_path,
            selection_source_fingerprint=self.selection_source_fingerprint,
        )
        if self.expected_source_path is not None:
            if source_identity is None:
                source_identity = SourceIdentityCatalog().identify(self.expected_source_path)
            if source_identity.sha256 != self.store.manifest.source_identity.sha256:
                raise ValueError(
                    "Analytical store source identity does not match the requested ELF: "
                    f"{self.expected_source_path}"
                )
        self.query_port = self.store
        from .jsonl_store import MaterializedDwarfIndex

        self.query_index = MaterializedDwarfIndex(self.store)
        self.dwarf_info = self.store.as_dwarf_info()
        self.platform = _platform(self.store.manifest.platform)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.close()

    def close(self) -> None:
        self.dwarf_info = None
        self.query_port = None
        self.query_index = None
        self.store = None


def _platform(value: str) -> ELFPlatform:
    try:
        return ELFPlatform(value.lower())
    except ValueError:
        return ELFPlatform.UNKNOWN


def load_analytical_store(
    manifest_path: Path,
    *,
    verify_source: bool = True,
    source_path: Path | None = None,
    allow_incomplete: bool = False,
    verify_artifacts: bool = False,
    selection_cache_path: Path | None = None,
    selection_source_fingerprint: dict[str, int | str] | None = None,
) -> JsonlDwarfStore:
    """Load the selected backend, requiring complete publication by default."""
    manifest = load_manifest(manifest_path.resolve())
    store_type: type[JsonlDwarfStore] = JsonlDwarfStore
    if "parquet" in manifest.files:
        from .parquet_store import ParquetDwarfStore

        store_type = ParquetDwarfStore
    return store_type.load(
        manifest_path,
        verify_source=verify_source,
        source_path=source_path,
        allow_incomplete=allow_incomplete,
        verify_artifacts=verify_artifacts,
        selection_cache_path=selection_cache_path,
        selection_source_fingerprint=selection_source_fingerprint,
    )

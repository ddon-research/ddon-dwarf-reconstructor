"""Generator session backed by a validated analytical DWARF store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...core.dwarf import DwarfInfo
from ...core.platform import ELFPlatform
from ...domain.ports.dwarf_lookup import DwarfLookupPort
from ..artifacts import SourceIdentityCatalog
from .doris import DorisConfig
from .doris_store import DorisDwarfIndex, DorisDwarfStore

if TYPE_CHECKING:
    from ...domain.ports.analytical_store import DwarfQueryPort


class AnalyticalDwarfSession:
    """Own one materialized store for the duration of a generation request."""

    # A store-backed runtime must never discover or consult the legacy dump
    # adapter implicitly. Validation producers remain available only through
    # an explicit non-analytical session.
    legacy_lookup_allowed = False

    def __init__(
        self,
        manifest_path: Path,
        *,
        expected_source_path: Path | None = None,
        verify_source: bool = True,
        selection_cache_path: Path | None = None,
        doris_config: DorisConfig | None = None,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.expected_source_path = expected_source_path.resolve() if expected_source_path else None
        self.verify_source = verify_source
        self.selection_cache_path = (
            selection_cache_path.resolve() if selection_cache_path is not None else None
        )
        self.selection_source_fingerprint: dict[str, int | str] | None = None
        self.doris_config = doris_config or DorisConfig.from_environment()
        self.store: DorisDwarfStore | None = None
        self.query_port: DwarfQueryPort | None = None
        self.query_index: DwarfLookupPort | None = None
        self.dwarf_info: DwarfInfo | None = None
        self.platform = ELFPlatform.UNKNOWN

    def __enter__(self) -> AnalyticalDwarfSession:
        source_identity = None
        if self.expected_source_path is not None and self.verify_source:
            source_identity = SourceIdentityCatalog().identify(self.expected_source_path)
            self.selection_source_fingerprint = source_identity.as_fingerprint()
        self.store = DorisDwarfStore.load(
            self.manifest_path,
            config=self.doris_config,
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
        self.query_index = DorisDwarfIndex(self.store)
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
        if self.store is not None:
            self.store.close()
        self.dwarf_info = None
        self.query_port = None
        self.query_index = None
        self.store = None


def load_analytical_store(*args: Any, **kwargs: Any) -> Any:
    """Load an artifact store for explicit inspection compatibility only.

    Generation never calls this wrapper; it opens :class:`DorisDwarfStore`
    directly. Keeping the old import location lazy preserves diagnostic and
    validation callers without reintroducing a file-backed runtime path.
    """
    from .artifact_store import load_analytical_store as load_artifact_store

    return load_artifact_store(*args, **kwargs)


def _platform(value: str) -> ELFPlatform:
    try:
        return ELFPlatform(value.lower())
    except ValueError:
        return ELFPlatform.UNKNOWN

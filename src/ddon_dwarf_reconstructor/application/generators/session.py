"""Application contract for an owned ELF/DWARF session."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ...core.dwarf import DwarfInfo
from ...core.platform import ELFPlatform
from ...domain.ports.analytical_store import DwarfQueryPort
from ...domain.ports.dwarf_lookup import DwarfLookupPort


class DwarfSession(Protocol):
    """Lifecycle and data contract required by the generation workflow."""

    dwarf_info: DwarfInfo | None
    platform: ELFPlatform
    query_port: DwarfQueryPort | None
    query_index: DwarfLookupPort | None

    def __enter__(self) -> DwarfSession: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None: ...

    def close(self) -> None: ...

    def begin_root(self, root_symbol: str) -> None: ...

    def end_root(self) -> None: ...


DwarfSessionFactory = Callable[[Path], DwarfSession]

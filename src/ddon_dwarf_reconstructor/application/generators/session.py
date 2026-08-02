"""Application contract for an owned ELF/DWARF session."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ...core.dwarf import DwarfInfo
from ...core.platform import ELFPlatform


class DwarfSession(Protocol):
    """Lifecycle and data contract required by the generation workflow."""

    dwarf_info: DwarfInfo | None
    platform: ELFPlatform

    def __enter__(self) -> DwarfSession: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None: ...

    def close(self) -> None: ...


DwarfSessionFactory = Callable[[Path], DwarfSession]

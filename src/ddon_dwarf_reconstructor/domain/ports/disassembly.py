"""Application-facing port for optional executable disassembly evidence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ..models.disassembly import OrbisDisassemblyReport


class DisassemblyProducerPort(Protocol):
    """Produce deterministic disassembly evidence for one root symbol."""

    def produce(self, elf_path: Path, root_symbol: str) -> OrbisDisassemblyReport: ...


DisassemblyProducerFactory = Callable[[Path], DisassemblyProducerPort]
